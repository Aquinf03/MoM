//! Timing / span hooks for measuring model work vs orchestration overhead.

use std::collections::HashMap;

use crate::schedule::SpecResult;
use serde_json::{json, Value};

/// What a span measures.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum SpanKind {
    /// Router / classifier hop.
    Router,
    /// Generator or other model hop.
    Model,
    /// Bus encode/decode.
    Bus,
    /// Wall time for an overlapped speculate step (max of router/prior).
    SpeculateWall,
}

impl SpanKind {
    /// Stable id for bindings / JSON.
    pub fn as_str(self) -> &'static str {
        match self {
            Self::Router => "router",
            Self::Model => "model",
            Self::Bus => "bus",
            Self::SpeculateWall => "speculate_wall",
        }
    }
}

/// One timed span.
#[derive(Debug, Clone)]
pub struct Span {
    /// Span name (usually node name or hop id).
    pub name: String,
    /// Kind of work.
    pub kind: SpanKind,
    /// Duration in milliseconds.
    pub duration_ms: f64,
}

/// Accumulated timing for one graph run.
#[derive(Debug, Clone, Default)]
pub struct Trace {
    /// Recorded spans in order.
    pub spans: Vec<Span>,
    /// Wall time for the full run.
    pub total_ms: f64,
    /// Sum of per-step critical-path contributions.
    pub critical_path_ms: f64,
    /// Estimated ms hidden by speculative overlap.
    pub overlap_saved_ms: f64,
    /// Speculative hit/miss by router node name.
    pub spec: HashMap<String, SpecResult>,
}

impl Trace {
    /// Empty trace.
    pub fn new() -> Self {
        Self::default()
    }

    /// Record an arbitrary span (does not advance critical path by itself).
    pub fn record(&mut self, name: impl Into<String>, kind: SpanKind, duration_ms: f64) {
        self.spans.push(Span {
            name: name.into(),
            kind,
            duration_ms,
        });
    }

    /// Record a sequential model/router hop on the critical path.
    pub fn record_sequential(
        &mut self,
        name: impl Into<String>,
        kind: SpanKind,
        duration_ms: f64,
    ) {
        let name = name.into();
        self.record(name, kind, duration_ms);
        self.critical_path_ms += duration_ms;
    }

    /// Record an overlapped speculate hop (router + prior).
    ///
    /// Critical path advances by `max(router_ms, prior_ms)`.
    pub fn record_speculate(
        &mut self,
        router: impl Into<String>,
        prior: impl Into<String>,
        router_ms: f64,
        prior_ms: f64,
        result: SpecResult,
    ) {
        let router = router.into();
        let prior = prior.into();
        self.record(router.clone(), SpanKind::Router, router_ms);
        self.record(prior.clone(), SpanKind::Model, prior_ms);
        let wall = router_ms.max(prior_ms);
        self.record(
            format!("{router}+{prior}"),
            SpanKind::SpeculateWall,
            wall,
        );
        self.critical_path_ms += wall;
        self.overlap_saved_ms += router_ms.min(prior_ms);
        self.spec.insert(router, result);
    }

    /// Add miss-path model time after a speculative miss.
    pub fn record_miss_model(&mut self, name: impl Into<String>, duration_ms: f64) {
        self.record_sequential(name, SpanKind::Model, duration_ms);
    }

    /// Finish the run with wall-clock total.
    pub fn finish(&mut self, total_ms: f64) {
        self.total_ms = total_ms;
    }

    /// Orchestration overhead: wall minus critical-path model/router work.
    pub fn orchestration_overhead_ms(&self) -> f64 {
        (self.total_ms - self.critical_path_ms).max(0.0)
    }

    /// Sum of router spans.
    pub fn router_ms(&self) -> f64 {
        self.spans
            .iter()
            .filter(|s| s.kind == SpanKind::Router)
            .map(|s| s.duration_ms)
            .sum()
    }

    /// Sum of model spans (includes speculative prior, even if discarded).
    pub fn model_ms(&self) -> f64 {
        self.spans
            .iter()
            .filter(|s| s.kind == SpanKind::Model)
            .map(|s| s.duration_ms)
            .sum()
    }

    /// JSON metrics blob for StateStore / Python.
    pub fn to_json(&self) -> Value {
        let node_ms: serde_json::Map<String, Value> = self
            .spans
            .iter()
            .filter(|s| s.kind == SpanKind::Router || s.kind == SpanKind::Model)
            .map(|s| (s.name.clone(), json!(s.duration_ms)))
            .collect();
        let spec: serde_json::Map<String, Value> = self
            .spec
            .iter()
            .map(|(k, v)| (k.clone(), json!(v.as_str())))
            .collect();
        let spans: Vec<Value> = self
            .spans
            .iter()
            .map(|s| {
                json!({
                    "name": s.name,
                    "kind": s.kind.as_str(),
                    "duration_ms": s.duration_ms,
                })
            })
            .collect();
        json!({
            "total_ms": self.total_ms,
            "critical_path_ms": self.critical_path_ms,
            "orchestration_overhead_ms": self.orchestration_overhead_ms(),
            "router_ms": self.router_ms(),
            "model_ms": self.model_ms(),
            "overlap_saved_ms": self.overlap_saved_ms,
            "node_ms": Value::Object(node_ms),
            "spec": Value::Object(spec),
            "spans": spans,
        })
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn overhead_on_speculate_hit() {
        let mut t = Trace::new();
        t.record_speculate("router", "gen", 50.0, 50.0, SpecResult::Hit);
        t.finish(52.0);
        assert!((t.critical_path_ms - 50.0).abs() < 1e-9);
        assert!((t.orchestration_overhead_ms() - 2.0).abs() < 1e-9);
        assert!((t.overlap_saved_ms - 50.0).abs() < 1e-9);
    }
}
