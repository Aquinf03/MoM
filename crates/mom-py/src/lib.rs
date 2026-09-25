//! Python extension module `mom._native` — thin surface over `mom-core`.

use std::sync::Arc;

use mom_core::StateStore;
use pyo3::exceptions::PyKeyError;
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

/// MoM native bindings.
#[pymodule]
fn _native(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add("__version__", mom_core::VERSION)?;
    m.add_function(wrap_pyfunction!(core_version, m)?)?;
    m.add_function(wrap_pyfunction!(ping, m)?)?;
    m.add_class::<PyStateStore>()?;
    Ok(())
}
