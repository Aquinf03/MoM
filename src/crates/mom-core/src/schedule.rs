//! Execution planning and speculative route-then-run scheduling helpers.

use std::collections::{HashMap, HashSet};
use std::time::Duration;

use crate::graph::{EdgeKind, Graph, GraphError};

/// One unit of scheduled work.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum Step {
    /// Run a single node to completion.
    Run {
        /// Node name.
        node: String,
    },
    /// Overlap router with a prior candidate; router output selects the winner.
    Speculate {
        /// Router node name.
        router: String,
        /// Speculative prior node (started with the router).
        prior: String,
    },
}

/// Ordered plan derived from a [`Graph`].
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ExecutionPlan {
    /// Steps in execution order.
    pub steps: Vec<Step>,
}

/// Failure building or interpreting a schedule.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum ScheduleError {
    /// Underlying graph error.
    Graph(GraphError),
    /// Router has more than one speculate edge (v1 limit).
    MultiplePriors {
        /// Router node.
        router: String,
    },
    /// Speculative prior is also a depend-successor in a conflicting way.
    ConflictingEdges {
        /// Node involved.
        node: String,
    },
}

impl std::fmt::Display for ScheduleError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Self::Graph(e) => write!(f, "{e}"),
            Self::MultiplePriors { router } => write!(
                f,
                "router '{router}' has multiple speculate priors (v1 supports one)"
            ),
            Self::ConflictingEdges { node } => {
                write!(f, "conflicting depend/speculate edges at node '{node}'")
            }
        }
    }
}

impl std::error::Error for ScheduleError {}

impl From<GraphError> for ScheduleError {
    fn from(value: GraphError) -> Self {
        Self::Graph(value)
    }
}

/// Build an [`ExecutionPlan`] from a graph.
///
/// Speculative pairs collapse into a single [`Step::Speculate`]. Remaining
/// nodes run in depend-topo order, skipping nodes already covered as priors.
pub fn plan(graph: &Graph) -> Result<ExecutionPlan, ScheduleError> {
    graph.validate()?;

    let mut prior_of_router: HashMap<String, String> = HashMap::new();
    let mut prior_nodes: HashSet<String> = HashSet::new();
    for (router, prior) in graph.speculative_pairs() {
        if prior_of_router.contains_key(&router) {
            return Err(ScheduleError::MultiplePriors { router });
        }
        // Prior should not also wait on router via depend (that would serialize).
        for e in &graph.edges {
            if e.kind == EdgeKind::Depend && e.from == router && e.to == prior {
                return Err(ScheduleError::ConflictingEdges { node: prior });
            }
        }
        prior_nodes.insert(prior.clone());
        prior_of_router.insert(router, prior);
    }

    let topo = graph.topo_order()?;
    let mut steps = Vec::new();
    let mut done: HashSet<String> = HashSet::new();

    for name in topo {
        if done.contains(&name) {
            continue;
        }
        if let Some(prior) = prior_of_router.get(&name) {
            steps.push(Step::Speculate {
                router: name.clone(),
                prior: prior.clone(),
            });
            done.insert(name);
            done.insert(prior.clone());
            continue;
        }
        if prior_nodes.contains(&name) {
            // Covered when its router step runs.
            continue;
        }
        steps.push(Step::Run { node: name.clone() });
        done.insert(name);
    }

    Ok(ExecutionPlan { steps })
}

/// Outcome of a speculative hop.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum SpecResult {
    /// Router selected the prior — overlapped work is kept.
    Hit,
    /// Router selected something else — prior discarded.
    Miss,
}

impl SpecResult {
    /// Stable id.
    pub fn as_str(self) -> &'static str {
        match self {
            Self::Hit => "hit",
            Self::Miss => "miss",
        }
    }
}

/// Timing / speculation metrics for one `run`.
#[derive(Debug, Clone, Default)]
pub struct RunMetrics {
    /// Wall time for the whole run.
    pub total: Duration,
    /// Per-node wall times.
    pub node_ms: HashMap<String, f64>,
    /// Speculative outcomes keyed by router node name.
    pub spec: HashMap<String, SpecResult>,
    /// Estimated overlapped ms saved on hits (min(router, prior) roughly).
    pub overlap_saved_ms: f64,
}

impl RunMetrics {
    /// Record a node duration in milliseconds.
    pub fn record_node(&mut self, node: impl Into<String>, ms: f64) {
        self.node_ms.insert(node.into(), ms);
    }

    /// Record speculation hit/miss for a router.
    pub fn record_spec(&mut self, router: impl Into<String>, result: SpecResult) {
        self.spec.insert(router.into(), result);
    }
}

/// Resolve router output into a route target string.
///
/// Accepts a plain string, or an object with a `route` / `model` / `node` field.
pub fn route_from_value(value: &serde_json::Value) -> Option<String> {
    if let Some(s) = value.as_str() {
        return Some(s.to_string());
    }
    let obj = value.as_object()?;
    for key in ["route", "model", "node", "target"] {
        if let Some(v) = obj.get(key) {
            if let Some(s) = v.as_str() {
                return Some(s.to_string());
            }
        }
    }
    None
}

/// Whether a route string matches the speculative prior node.
pub fn route_matches_prior(
    route: &str,
    prior_name: &str,
    prior_model_id: &str,
) -> bool {
    route == prior_name || route == prior_model_id
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn plan_speculate_collapses() {
        let mut g = Graph::new();
        g.add("router", "stub.router");
        g.add("gen", "stub.echo");
        g.speculate("router", "gen");
        let p = plan(&g).unwrap();
        assert_eq!(
            p.steps,
            vec![Step::Speculate {
                router: "router".into(),
                prior: "gen".into(),
            }]
        );
    }

    #[test]
    fn plan_sequence() {
        let mut g = Graph::new();
        g.add("a", "ma");
        g.add("b", "mb");
        g.link("a", "b");
        let p = plan(&g).unwrap();
        assert_eq!(
            p.steps,
            vec![
                Step::Run {
                    node: "a".into()
                },
                Step::Run {
                    node: "b".into()
                }
            ]
        );
    }

    #[test]
    fn route_parsing() {
        assert_eq!(
            route_from_value(&json!("stub.echo")).as_deref(),
            Some("stub.echo")
        );
        assert_eq!(
            route_from_value(&json!({"route": "gen"})).as_deref(),
            Some("gen")
        );
        assert!(route_matches_prior("gen", "gen", "stub.echo"));
        assert!(route_matches_prior("stub.echo", "gen", "stub.echo"));
        assert!(!route_matches_prior("other", "gen", "stub.echo"));
    }
}
