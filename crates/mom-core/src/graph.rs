//! Graph as runtime data — nodes reference model directory ids.

use std::collections::{HashMap, HashSet, VecDeque};

/// How an edge constrains execution.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum EdgeKind {
    /// `to` waits for `from` to finish (normal pipeline).
    Depend,
    /// Start `to` when `from` starts (speculative overlap). Router `from`
    /// later confirms or rejects `to`.
    Speculate,
}

impl EdgeKind {
    /// Stable id for bindings / serialization.
    pub fn as_str(self) -> &'static str {
        match self {
            Self::Depend => "depend",
            Self::Speculate => "speculate",
        }
    }

    /// Parse from string.
    pub fn parse(s: &str) -> Option<Self> {
        match s {
            "depend" | "sequence" | "then" => Some(Self::Depend),
            "speculate" | "spec" => Some(Self::Speculate),
            _ => None,
        }
    }
}

/// A hop in the pipeline.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Node {
    /// Local name within the graph.
    pub name: String,
    /// Id in the model directory.
    pub model_id: String,
}

/// Directed edge between nodes.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Edge {
    /// Source node name.
    pub from: String,
    /// Destination node name.
    pub to: String,
    /// Depend vs speculate.
    pub kind: EdgeKind,
}

/// Pipeline topology (not hardcoded shapes).
#[derive(Debug, Clone, Default, PartialEq, Eq)]
pub struct Graph {
    /// Nodes in insertion order.
    pub nodes: Vec<Node>,
    /// Edges in insertion order.
    pub edges: Vec<Edge>,
}

impl Graph {
    /// Empty graph.
    pub fn new() -> Self {
        Self::default()
    }

    /// Add a node.
    pub fn add(&mut self, name: impl Into<String>, model_id: impl Into<String>) -> &mut Self {
        self.nodes.push(Node {
            name: name.into(),
            model_id: model_id.into(),
        });
        self
    }

    /// Depend edge: `to` waits on `from`.
    pub fn link(&mut self, from: impl Into<String>, to: impl Into<String>) -> &mut Self {
        self.edges.push(Edge {
            from: from.into(),
            to: to.into(),
            kind: EdgeKind::Depend,
        });
        self
    }

    /// Speculate edge: start `prior` when `router` starts.
    pub fn speculate(
        &mut self,
        router: impl Into<String>,
        prior: impl Into<String>,
    ) -> &mut Self {
        self.edges.push(Edge {
            from: router.into(),
            to: prior.into(),
            kind: EdgeKind::Speculate,
        });
        self
    }

    /// Look up a node by name.
    pub fn node(&self, name: &str) -> Option<&Node> {
        self.nodes.iter().find(|n| n.name == name)
    }

    /// All node names.
    pub fn names(&self) -> HashSet<String> {
        self.nodes.iter().map(|n| n.name.clone()).collect()
    }

    /// Validate names on edges exist; no duplicate node names.
    pub fn validate(&self) -> Result<(), GraphError> {
        let mut seen = HashSet::new();
        for n in &self.nodes {
            if !seen.insert(n.name.clone()) {
                return Err(GraphError::DuplicateNode(n.name.clone()));
            }
        }
        let names = self.names();
        for e in &self.edges {
            if !names.contains(&e.from) {
                return Err(GraphError::UnknownNode(e.from.clone()));
            }
            if !names.contains(&e.to) {
                return Err(GraphError::UnknownNode(e.to.clone()));
            }
            if e.from == e.to {
                return Err(GraphError::SelfEdge(e.from.clone()));
            }
        }
        Ok(())
    }

    /// Kahn topo order using **depend** edges only (speculate does not block).
    pub fn topo_order(&self) -> Result<Vec<String>, GraphError> {
        self.validate()?;
        let names = self.names();
        let mut indeg: HashMap<String, usize> =
            names.iter().map(|n| (n.clone(), 0usize)).collect();
        let mut adj: HashMap<String, Vec<String>> =
            names.iter().map(|n| (n.clone(), Vec::new())).collect();

        for e in &self.edges {
            if e.kind != EdgeKind::Depend {
                continue;
            }
            *indeg.get_mut(&e.to).expect("validated") += 1;
            adj.get_mut(&e.from).expect("validated").push(e.to.clone());
        }

        let mut q: VecDeque<String> = indeg
            .iter()
            .filter(|(_, d)| **d == 0)
            .map(|(n, _)| n.clone())
            .collect();
        // Stable-ish: prefer insertion order among ready nodes
        let order_index: HashMap<&str, usize> = self
            .nodes
            .iter()
            .enumerate()
            .map(|(i, n)| (n.name.as_str(), i))
            .collect();
        let mut q_vec: Vec<String> = q.drain(..).collect();
        q_vec.sort_by_key(|n| order_index[n.as_str()]);
        q.extend(q_vec);

        let mut out = Vec::with_capacity(self.nodes.len());
        while let Some(n) = q.pop_front() {
            out.push(n.clone());
            let children = adj.get(&n).cloned().unwrap_or_default();
            let mut ready = Vec::new();
            for c in children {
                let d = indeg.get_mut(&c).expect("validated");
                *d -= 1;
                if *d == 0 {
                    ready.push(c);
                }
            }
            ready.sort_by_key(|n| order_index[n.as_str()]);
            q.extend(ready);
        }

        if out.len() != self.nodes.len() {
            return Err(GraphError::Cycle);
        }
        Ok(out)
    }

    /// Speculative (router → prior) pairs declared on the graph.
    pub fn speculative_pairs(&self) -> Vec<(String, String)> {
        self.edges
            .iter()
            .filter(|e| e.kind == EdgeKind::Speculate)
            .map(|e| (e.from.clone(), e.to.clone()))
            .collect()
    }

    /// Build from a JSON object `{nodes: [...], edges: [...]}`.
    pub fn from_json(value: &serde_json::Value) -> Result<Self, GraphError> {
        let obj = value
            .as_object()
            .ok_or_else(|| GraphError::InvalidJson("expected object".into()))?;
        let mut g = Graph::new();
        if let Some(nodes) = obj.get("nodes").and_then(|n| n.as_array()) {
            for n in nodes {
                let name = n
                    .get("name")
                    .and_then(|v| v.as_str())
                    .ok_or_else(|| GraphError::InvalidJson("node missing name".into()))?;
                let model_id = n
                    .get("model_id")
                    .and_then(|v| v.as_str())
                    .ok_or_else(|| GraphError::InvalidJson(format!("node '{name}' missing model_id")))?;
                g.add(name, model_id);
            }
        }
        if let Some(edges) = obj.get("edges").and_then(|n| n.as_array()) {
            for e in edges {
                let from = e
                    .get("from")
                    .or_else(|| e.get("frm"))
                    .and_then(|v| v.as_str())
                    .ok_or_else(|| GraphError::InvalidJson("edge missing from".into()))?;
                let to = e
                    .get("to")
                    .and_then(|v| v.as_str())
                    .ok_or_else(|| GraphError::InvalidJson("edge missing to".into()))?;
                let kind = e
                    .get("kind")
                    .and_then(|v| v.as_str())
                    .and_then(EdgeKind::parse)
                    .unwrap_or(EdgeKind::Depend);
                match kind {
                    EdgeKind::Depend => {
                        g.link(from, to);
                    }
                    EdgeKind::Speculate => {
                        g.speculate(from, to);
                    }
                }
            }
        }
        g.validate()?;
        Ok(g)
    }

    /// Serialize to JSON for bindings.
    pub fn to_json(&self) -> serde_json::Value {
        serde_json::json!({
            "nodes": self.nodes.iter().map(|n| serde_json::json!({
                "name": n.name,
                "model_id": n.model_id,
            })).collect::<Vec<_>>(),
            "edges": self.edges.iter().map(|e| serde_json::json!({
                "from": e.from,
                "to": e.to,
                "kind": e.kind.as_str(),
            })).collect::<Vec<_>>(),
        })
    }
}

/// Graph structural error.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum GraphError {
    /// Two nodes share a name.
    DuplicateNode(String),
    /// Edge references a missing node.
    UnknownNode(String),
    /// Edge from a node to itself.
    SelfEdge(String),
    /// Depend edges form a cycle.
    Cycle,
    /// JSON graph payload was malformed.
    InvalidJson(String),
}

impl std::fmt::Display for GraphError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Self::DuplicateNode(n) => write!(f, "duplicate node name: {n}"),
            Self::UnknownNode(n) => write!(f, "unknown node: {n}"),
            Self::SelfEdge(n) => write!(f, "self-edge on node: {n}"),
            Self::Cycle => write!(f, "depend edges contain a cycle"),
            Self::InvalidJson(msg) => write!(f, "invalid graph json: {msg}"),
        }
    }
}

impl std::error::Error for GraphError {}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn topo_ignores_speculate() {
        let mut g = Graph::new();
        g.add("router", "r");
        g.add("gen", "g");
        g.speculate("router", "gen");
        assert_eq!(g.topo_order().unwrap(), vec!["router", "gen"]);
    }

    #[test]
    fn topo_depend() {
        let mut g = Graph::new();
        g.add("a", "ma");
        g.add("b", "mb");
        g.add("c", "mc");
        g.link("a", "b");
        g.link("b", "c");
        assert_eq!(g.topo_order().unwrap(), vec!["a", "b", "c"]);
    }
}
