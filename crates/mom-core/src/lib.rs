//! MoM core — colocated hot path.
//!
//! Owns shared state, graph execution, and speculative scheduling.
//! Topology and model kinds stay outside: graphs reference directory ids;
//! adapters live in the Python/`models/` surface.

#![deny(missing_docs)]

mod bus;
mod state;

pub use bus::{
    Bus, BusError, EmbeddingTransport, Payload, PayloadKind, TextJsonTransport, Transport,
};
pub use state::StateStore;

/// Crate version (kept in sync with the workspace package version).
pub const VERSION: &str = env!("CARGO_PKG_VERSION");

/// Hot-path liveness check.
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
