//! Python extension module `mom._native` — thin surface over `mom-core`.

use pyo3::prelude::*;

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

/// MoM native bindings.
#[pymodule]
fn _native(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add("__version__", mom_core::VERSION)?;
    m.add_function(wrap_pyfunction!(core_version, m)?)?;
    m.add_function(wrap_pyfunction!(ping, m)?)?;
    Ok(())
}
