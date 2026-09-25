//! Python extension module `mom._native` — thin surface over `mom-core`.

use std::collections::HashMap;
use std::sync::Arc;
use std::thread;
use std::time::Instant;

use mom_core::{
    plan, route_from_value, route_matches_prior as route_matches_prior_core, Bus, Graph, Payload,
    SpecResult, StateStore, Step, Trace,
};
use pyo3::exceptions::{PyKeyError, PyValueError};
use pyo3::prelude::*;
use pyo3::types::PyDict;
use pythonize::{depythonize, pythonize};
use serde_json::Value;

/// Return the mom-core crate version string.
#[pyfunction]
fn core_version() -> &'static str {
    mom_core::VERSION
}

/// Hot-path ping (proves the native extension loaded).
#[pyfunction]
fn ping() -> &'static str {
    mom_core::ping()
}

fn bus_err(err: mom_core::BusError) -> PyErr {
    PyValueError::new_err(err.to_string())
}

fn schedule_err(err: impl std::fmt::Display) -> PyErr {
    PyValueError::new_err(err.to_string())
}

/// Build an execution plan from a graph dict `{nodes, edges}`.
#[pyfunction]
fn plan_graph(py: Python<'_>, graph: &Bound<'_, PyAny>) -> PyResult<PyObject> {
    let v: Value = depythonize(graph)?;
    let g = Graph::from_json(&v).map_err(schedule_err)?;
    let plan = plan(&g).map_err(schedule_err)?;
    let steps: Vec<Value> = plan
        .steps
        .iter()
        .map(|s| match s {
            Step::Run { node } => serde_json::json!({"type": "run", "node": node}),
            Step::Speculate { router, prior } => serde_json::json!({
                "type": "speculate",
                "router": router,
                "prior": prior,
            }),
        })
        .collect();
    Ok(pythonize(py, &serde_json::json!({ "steps": steps }))?.unbind())
}

/// Parse router output into a route string (`None` if missing).
#[pyfunction]
fn route_from(value: &Bound<'_, PyAny>) -> PyResult<Option<String>> {
    let v: Value = depythonize(value)?;
    Ok(route_from_value(&v))
}

/// Whether `route` matches speculative prior name or model id.
#[pyfunction]
fn route_matches_prior(route: &str, prior_name: &str, prior_model_id: &str) -> bool {
    route_matches_prior_core(route, prior_name, prior_model_id)
}

/// Single-owner shared state — models read/write by key.
#[pyclass(name = "StateStore")]
#[derive(Clone)]
struct PyStateStore {
    inner: Arc<StateStore>,
}

impl PyStateStore {
    fn from_arc(inner: Arc<StateStore>) -> Self {
        Self { inner }
    }

    fn store(&self) -> &StateStore {
        self.inner.as_ref()
    }
}

#[pymethods]
impl PyStateStore {
    #[new]
    fn new() -> Self {
        Self::from_arc(Arc::new(StateStore::new()))
    }

    fn get(&self, py: Python<'_>, key: &str) -> PyResult<PyObject> {
        match self.store().get(key) {
            Some(value) => Ok(pythonize(py, &value)?.unbind()),
            None => Ok(py.None()),
        }
    }

    fn set(&self, key: &str, value: &Bound<'_, PyAny>) -> PyResult<()> {
        let v: Value = depythonize(value)?;
        self.store().set(key, v);
        Ok(())
    }

    fn remove(&self, py: Python<'_>, key: &str) -> PyResult<PyObject> {
        match self.store().remove(key) {
            Some(value) => Ok(pythonize(py, &value)?.unbind()),
            None => Ok(py.None()),
        }
    }

    fn contains(&self, key: &str) -> bool {
        self.store().contains(key)
    }

    fn keys(&self) -> Vec<String> {
        self.store().keys()
    }

    fn __len__(&self) -> usize {
        self.store().len()
    }

    fn clear(&self) {
        self.store().clear();
    }

    fn snapshot(&self, py: Python<'_>) -> PyResult<PyObject> {
        Ok(pythonize(py, &self.store().snapshot())?.unbind())
    }

    fn __contains__(&self, key: &str) -> bool {
        self.contains(key)
    }

    fn __getitem__(&self, py: Python<'_>, key: &str) -> PyResult<PyObject> {
        match self.store().get(key) {
            Some(value) => Ok(pythonize(py, &value)?.unbind()),
            None => Err(PyKeyError::new_err(key.to_string())),
        }
    }

    fn __setitem__(&self, key: &str, value: &Bound<'_, PyAny>) -> PyResult<()> {
        self.set(key, value)
    }

    fn __delitem__(&self, key: &str) -> PyResult<()> {
        if self.store().remove(key).is_none() {
            return Err(PyKeyError::new_err(key.to_string()));
        }
        Ok(())
    }

    fn __repr__(&self) -> String {
        format!("StateStore(len={})", self.store().len())
    }
}

/// Registered model callable: `(input, state) -> output`.
struct NativeEntry {
    call: Py<PyAny>,
    tags: Vec<String>,
    #[allow(dead_code)]
    meta: Value,
}

/// Model directory — register Python callables by id.
#[pyclass(name = "ModelDirectory")]
struct PyModelDirectory {
    entries: HashMap<String, NativeEntry>,
}

#[pymethods]
impl PyModelDirectory {
    #[new]
    fn new() -> Self {
        Self {
            entries: HashMap::new(),
        }
    }

    /// Register `callable(input, state) -> output` under `id`.
    #[pyo3(signature = (id, callable, *, tags = None))]
    fn register(
        &mut self,
        id: String,
        callable: Bound<'_, PyAny>,
        tags: Option<Vec<String>>,
    ) -> PyResult<()> {
        if self.entries.contains_key(&id) {
            return Err(PyValueError::new_err(format!(
                "model already registered: {id}"
            )));
        }
        if !callable.is_callable() {
            return Err(PyValueError::new_err("register() requires a callable"));
        }
        self.entries.insert(
            id,
            NativeEntry {
                call: callable.unbind(),
                tags: tags.unwrap_or_default(),
                meta: Value::Object(Default::default()),
            },
        );
        Ok(())
    }

    fn ids(&self) -> Vec<String> {
        let mut ids: Vec<String> = self.entries.keys().cloned().collect();
        ids.sort();
        ids
    }

    fn __contains__(&self, id: &str) -> bool {
        self.entries.contains_key(id)
    }

    fn __len__(&self) -> usize {
        self.entries.len()
    }

    fn tags(&self, id: &str) -> PyResult<Vec<String>> {
        self.entries
            .get(id)
            .map(|e| e.tags.clone())
            .ok_or_else(|| PyKeyError::new_err(id.to_string()))
    }

    fn __repr__(&self) -> String {
        format!("ModelDirectory(len={})", self.entries.len())
    }
}

/// Hop payload (opaque bytes + kind).
#[pyclass(name = "Payload")]
#[derive(Clone)]
struct PyPayload {
    inner: Payload,
}

#[pymethods]
impl PyPayload {
    fn kind(&self) -> &'static str {
        self.inner.kind().as_str()
    }

    fn body<'py>(&self, py: Python<'py>) -> Bound<'py, pyo3::types::PyBytes> {
        pyo3::types::PyBytes::new(py, self.inner.body())
    }

    fn as_text(&self) -> PyResult<String> {
        self.inner
            .as_text()
            .map(str::to_owned)
            .map_err(bus_err)
    }

    fn __repr__(&self) -> String {
        format!(
            "Payload(kind={}, len={})",
            self.inner.kind().as_str(),
            self.inner.body().len()
        )
    }
}

/// Hop bus with a pluggable transport (default: text/JSON).
#[pyclass(name = "Bus")]
#[derive(Clone)]
struct PyBus {
    inner: Bus,
}

#[pymethods]
impl PyBus {
    #[new]
    #[pyo3(signature = (transport = "text_json"))]
    fn new(transport: &str) -> PyResult<Self> {
        let inner = match transport {
            "text_json" | "text" | "json" => Bus::text_json(),
            "embedding" | "embeddings" => Bus::embedding(),
            other => {
                return Err(PyValueError::new_err(format!(
                    "unknown transport '{other}'; expected 'text_json' or 'embedding'"
                )))
            }
        };
        Ok(Self { inner })
    }

    #[staticmethod]
    fn text_json() -> Self {
        Self {
            inner: Bus::text_json(),
        }
    }

    #[staticmethod]
    fn embedding() -> Self {
        Self {
            inner: Bus::embedding(),
        }
    }

    fn kind(&self) -> &'static str {
        self.inner.kind().as_str()
    }

    fn encode(&self, value: &Bound<'_, PyAny>) -> PyResult<PyPayload> {
        let v: Value = depythonize(value)?;
        let payload = self.inner.encode(&v).map_err(bus_err)?;
        Ok(PyPayload { inner: payload })
    }

    fn decode(&self, py: Python<'_>, payload: &PyPayload) -> PyResult<PyObject> {
        let v = self.inner.decode(&payload.inner).map_err(bus_err)?;
        Ok(pythonize(py, &v)?.unbind())
    }

    fn roundtrip(&self, py: Python<'_>, value: &Bound<'_, PyAny>) -> PyResult<PyObject> {
        let v: Value = depythonize(value)?;
        let out = self.inner.roundtrip(&v).map_err(bus_err)?;
        Ok(pythonize(py, &out)?.unbind())
    }

    fn __repr__(&self) -> String {
        format!("Bus(kind={})", self.inner.kind().as_str())
    }
}

fn call_model(
    py: Python<'_>,
    directory: &PyModelDirectory,
    model_id: &str,
    input: Bound<'_, PyAny>,
    state: PyStateStore,
) -> PyResult<(PyObject, f64)> {
    let entry = directory.entries.get(model_id).ok_or_else(|| {
        PyKeyError::new_err(format!("unknown model: {model_id}"))
    })?;
    let t0 = Instant::now();
    let out = entry.call.call1(py, (input, state))?;
    let ms = t0.elapsed().as_secs_f64() * 1000.0;
    Ok((out.into(), ms))
}

fn resolve_model_id(graph: &Graph, route: &str) -> Option<String> {
    for n in &graph.nodes {
        if n.name == route || n.model_id == route {
            return Some(n.model_id.clone());
        }
    }
    Some(route.to_string())
}

/// Execute a graph via native planner + registered callables.
///
/// `models` maps model_id → `(input, state) -> output`.
/// Returns `{output, metrics}` with span / orchestration overhead.
#[pyfunction]
#[pyo3(signature = (graph, input, models, state=None, bus=None))]
fn run_graph(
    py: Python<'_>,
    graph: &Bound<'_, PyAny>,
    input: Bound<'_, PyAny>,
    models: &Bound<'_, PyModelDirectory>,
    state: Option<Bound<'_, PyStateStore>>,
    bus: Option<Bound<'_, PyBus>>,
) -> PyResult<PyObject> {
    let graph_v: Value = depythonize(graph)?;
    let g = Graph::from_json(&graph_v).map_err(schedule_err)?;
    let exec = plan(&g).map_err(schedule_err)?;
    // Clone Arc handles — do not move the caller's Python objects out.
    let state: PyStateStore = match state {
        Some(b) => b.borrow().clone(),
        None => PyStateStore::new(),
    };
    let bus: PyBus = match bus {
        Some(b) => b.borrow().clone(),
        None => PyBus::text_json(),
    };
    let directory = models.borrow();

    let mut trace = Trace::new();
    let run_t0 = Instant::now();
    let mut current: PyObject = input.unbind();

    for step in &exec.steps {
        match step {
            Step::Run { node } => {
                let n = g
                    .node(node)
                    .ok_or_else(|| PyValueError::new_err(format!("missing node {node}")))?;
                let t_bus = Instant::now();
                let encoded = {
                    let bound = current.bind(py);
                    bus.encode(bound)?
                };
                let decoded = bus.decode(py, &encoded)?;
                trace.record(
                    format!("bus:{node}"),
                    mom_core::SpanKind::Bus,
                    t_bus.elapsed().as_secs_f64() * 1000.0,
                );
                let (out, ms) = call_model(
                    py,
                    &directory,
                    &n.model_id,
                    decoded.bind(py).clone(),
                    state.clone(),
                )?;
                let kind = if directory
                    .entries
                    .get(&n.model_id)
                    .map(|e| e.tags.iter().any(|t| t == "router"))
                    .unwrap_or(false)
                {
                    mom_core::SpanKind::Router
                } else {
                    mom_core::SpanKind::Model
                };
                trace.record_sequential(node.clone(), kind, ms);
                current = out;
            }
            Step::Speculate { router, prior } => {
                let router_node = g.node(router).ok_or_else(|| {
                    PyValueError::new_err(format!("missing router node {router}"))
                })?;
                let prior_node = g
                    .node(prior)
                    .ok_or_else(|| PyValueError::new_err(format!("missing prior node {prior}")))?;

                let t_bus = Instant::now();
                let encoded = {
                    let bound = current.bind(py);
                    bus.encode(bound)?
                };
                let decoded = bus.decode(py, &encoded)?;
                trace.record(
                    format!("bus:{router}+{prior}"),
                    mom_core::SpanKind::Bus,
                    t_bus.elapsed().as_secs_f64() * 1000.0,
                );

                // Clone handles for overlapped prior thread.
                let prior_call = directory
                    .entries
                    .get(&prior_node.model_id)
                    .ok_or_else(|| {
                        PyKeyError::new_err(format!("unknown model: {}", prior_node.model_id))
                    })?
                    .call
                    .clone_ref(py);
                let state_arc = state.inner.clone();
                let input_for_prior: Value = depythonize(decoded.bind(py))?;
                let input_for_router = decoded;

                let prior_handle = thread::spawn(move || {
                    Python::with_gil(|py| {
                        let state = PyStateStore::from_arc(state_arc);
                        let input_obj = pythonize(py, &input_for_prior)?;
                        let t0 = Instant::now();
                        let out = prior_call.call1(py, (input_obj, state))?;
                        let ms = t0.elapsed().as_secs_f64() * 1000.0;
                        Ok::<(PyObject, f64), PyErr>((out.into(), ms))
                    })
                });

                let (route_out, router_ms) = call_model(
                    py,
                    &directory,
                    &router_node.model_id,
                    input_for_router.bind(py).clone(),
                    state.clone(),
                )?;
                // Release the GIL while joining so the prior thread can finish.
                let (prior_out, prior_ms) = py.allow_threads(|| {
                    prior_handle
                        .join()
                        .map_err(|_| PyValueError::new_err("prior thread panicked"))?
                })?;

                let route_val: Value = depythonize(route_out.bind(py))?;
                let route = route_from_value(&route_val).ok_or_else(|| {
                    PyValueError::new_err(format!("router '{router}' did not return a route"))
                })?;

                if route_matches_prior(&route, prior, &prior_node.model_id) {
                    trace.record_speculate(
                        router.clone(),
                        prior.clone(),
                        router_ms,
                        prior_ms,
                        SpecResult::Hit,
                    );
                    current = prior_out;
                } else {
                    trace.record_speculate(
                        router.clone(),
                        prior.clone(),
                        router_ms,
                        prior_ms,
                        SpecResult::Miss,
                    );
                    let model_id = resolve_model_id(&g, &route).ok_or_else(|| {
                        PyValueError::new_err(format!("cannot resolve route '{route}'"))
                    })?;
                    if !directory.entries.contains_key(&model_id) {
                        return Err(PyKeyError::new_err(format!(
                            "route '{route}' not in directory"
                        )));
                    }
                    let rein = bus.decode(py, &encoded)?;
                    let (out, ms) = call_model(
                        py,
                        &directory,
                        &model_id,
                        rein.bind(py).clone(),
                        state.clone(),
                    )?;
                    trace.record_miss_model(route, ms);
                    current = out;
                }
            }
        }
    }

    trace.finish(run_t0.elapsed().as_secs_f64() * 1000.0);
    let metrics = trace.to_json();
    state.store().set("mom.metrics", metrics.clone());

    let out = PyDict::new(py);
    out.set_item("output", current)?;
    out.set_item("metrics", pythonize(py, &metrics)?)?;
    out.set_item("state", state)?;
    Ok(out.unbind().into())
}

/// MoM native bindings.
#[pymodule]
fn _native(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add("__version__", mom_core::VERSION)?;
    m.add_function(wrap_pyfunction!(core_version, m)?)?;
    m.add_function(wrap_pyfunction!(ping, m)?)?;
    m.add_function(wrap_pyfunction!(plan_graph, m)?)?;
    m.add_function(wrap_pyfunction!(route_from, m)?)?;
    m.add_function(wrap_pyfunction!(route_matches_prior, m)?)?;
    m.add_function(wrap_pyfunction!(run_graph, m)?)?;
    m.add_class::<PyStateStore>()?;
    m.add_class::<PyModelDirectory>()?;
    m.add_class::<PyBus>()?;
    m.add_class::<PyPayload>()?;
    Ok(())
}
