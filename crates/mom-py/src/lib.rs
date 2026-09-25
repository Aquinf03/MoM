//! Python extension module `mom._native` — thin surface over `mom-core`.

use std::sync::Arc;

use mom_core::{Bus, Payload, StateStore};
use pyo3::exceptions::{PyKeyError, PyValueError};
use pyo3::prelude::*;
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

/// Single-owner shared state — models read/write by key.
#[pyclass(name = "StateStore")]
struct PyStateStore {
    inner: Arc<StateStore>,
}

impl PyStateStore {
    fn store(&self) -> &StateStore {
        self.inner.as_ref()
    }
}

#[pymethods]
impl PyStateStore {
    #[new]
    fn new() -> Self {
        Self {
            inner: Arc::new(StateStore::new()),
        }
    }

    /// Read a JSON-compatible value by key (`None` if missing).
    fn get(&self, py: Python<'_>, key: &str) -> PyResult<PyObject> {
        match self.store().get(key) {
            Some(value) => Ok(pythonize(py, &value)?.unbind()),
            None => Ok(py.None()),
        }
    }

    /// Write a JSON-compatible value by key.
    fn set(&self, key: &str, value: &Bound<'_, PyAny>) -> PyResult<()> {
        let v: Value = depythonize(value)?;
        self.store().set(key, v);
        Ok(())
    }

    /// Remove a key; returns the previous value or `None`.
    fn remove(&self, py: Python<'_>, key: &str) -> PyResult<PyObject> {
        match self.store().remove(key) {
            Some(value) => Ok(pythonize(py, &value)?.unbind()),
            None => Ok(py.None()),
        }
    }

    /// True if `key` is present.
    fn contains(&self, key: &str) -> bool {
        self.store().contains(key)
    }

    /// Sorted keys.
    fn keys(&self) -> Vec<String> {
        self.store().keys()
    }

    /// Entry count.
    fn __len__(&self) -> usize {
        self.store().len()
    }

    fn clear(&self) {
        self.store().clear();
    }

    /// Full snapshot as a Python dict (export only — store remains authoritative).
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

/// Hop payload (opaque bytes + kind).
#[pyclass(name = "Payload")]
#[derive(Clone)]
struct PyPayload {
    inner: Payload,
}

#[pymethods]
impl PyPayload {
    /// Transport kind id (`text_json` | `embedding`).
    fn kind(&self) -> &'static str {
        self.inner.kind().as_str()
    }

    /// Raw body bytes.
    fn body<'py>(&self, py: Python<'py>) -> Bound<'py, pyo3::types::PyBytes> {
        pyo3::types::PyBytes::new(py, self.inner.body())
    }

    /// UTF-8 body when this is a text payload.
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
    /// Create a bus. `transport` is `"text_json"` (default) or `"embedding"`.
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

    /// Active transport kind.
    fn kind(&self) -> &'static str {
        self.inner.kind().as_str()
    }

    /// Encode a JSON-compatible Python value into a Payload.
    fn encode(&self, value: &Bound<'_, PyAny>) -> PyResult<PyPayload> {
        let v: Value = depythonize(value)?;
        let payload = self.inner.encode(&v).map_err(bus_err)?;
        Ok(PyPayload { inner: payload })
    }

    /// Decode a Payload into a Python value.
    fn decode(&self, py: Python<'_>, payload: &PyPayload) -> PyResult<PyObject> {
        let v = self.inner.decode(&payload.inner).map_err(bus_err)?;
        Ok(pythonize(py, &v)?.unbind())
    }

    /// Encode then decode.
    fn roundtrip(&self, py: Python<'_>, value: &Bound<'_, PyAny>) -> PyResult<PyObject> {
        let v: Value = depythonize(value)?;
        let out = self.inner.roundtrip(&v).map_err(bus_err)?;
        Ok(pythonize(py, &out)?.unbind())
    }

    fn __repr__(&self) -> String {
        format!("Bus(kind={})", self.inner.kind().as_str())
    }
}

/// MoM native bindings.
#[pymodule]
fn _native(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add("__version__", mom_core::VERSION)?;
    m.add_function(wrap_pyfunction!(core_version, m)?)?;
    m.add_function(wrap_pyfunction!(ping, m)?)?;
    m.add_class::<PyStateStore>()?;
    m.add_class::<PyBus>()?;
    m.add_class::<PyPayload>()?;
    Ok(())
}
