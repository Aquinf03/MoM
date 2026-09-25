//! MoM core — colocated hot path.
//!
//! Owns shared state, graph execution, and speculative scheduling.
//! Topology and model kinds stay outside: graphs reference directory ids;
//! adapters live in the Python/`models/` surface.

#![deny(missing_docs)]

/// Crate version (kept in sync with the workspace package version).
pub const VERSION: &str = env!("CARGO_PKG_VERSION");

/// Placeholder until StateStore / Graph / Scheduler land.
pub fn ping() -> &'static str {
    "mom-core"
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn ping_ok() {
        assert_eq!(ping(), "mom-core");
    }
}
