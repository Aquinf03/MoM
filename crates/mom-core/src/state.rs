//! Single-owner shared state for colocated model composition.
//!
//! Models read and write by key against this store. State is not passed as
//! messages between hops — the store is the sole authority for “what happened.”

use std::collections::HashMap;
use std::sync::RwLock;

use serde_json::Value;

/// In-memory key/value store shared by all models in a colocated run.
///
/// Values are JSON ([`serde_json::Value`]) so the text-native bus and Python
/// boundary stay aligned without per-model serialization ownership.
#[derive(Debug, Default)]
pub struct StateStore {
    inner: RwLock<HashMap<String, Value>>,
}

impl StateStore {
    /// Create an empty store.
    pub fn new() -> Self {
        Self::default()
    }

    /// Read a value by key.
    pub fn get(&self, key: &str) -> Option<Value> {
        self.inner
            .read()
            .expect("state store lock poisoned")
            .get(key)
            .cloned()
    }

    /// Write (or overwrite) a value by key.
    pub fn set(&self, key: impl Into<String>, value: Value) {
        self.inner
            .write()
            .expect("state store lock poisoned")
            .insert(key.into(), value);
    }

    /// Remove a key; returns the previous value if any.
    pub fn remove(&self, key: &str) -> Option<Value> {
        self.inner
            .write()
            .expect("state store lock poisoned")
            .remove(key)
    }

    /// Whether `key` is present.
    pub fn contains(&self, key: &str) -> bool {
        self.inner
            .read()
            .expect("state store lock poisoned")
            .contains_key(key)
    }

    /// Sorted list of keys currently in the store.
    pub fn keys(&self) -> Vec<String> {
        let mut keys: Vec<String> = self
            .inner
            .read()
            .expect("state store lock poisoned")
            .keys()
            .cloned()
            .collect();
        keys.sort();
        keys
    }

    /// Number of entries.
    pub fn len(&self) -> usize {
        self.inner
            .read()
            .expect("state store lock poisoned")
            .len()
    }

    /// True when the store has no entries.
    pub fn is_empty(&self) -> bool {
        self.len() == 0
    }

    /// Drop all entries.
    pub fn clear(&self) {
        self.inner
            .write()
            .expect("state store lock poisoned")
            .clear();
    }

    /// Snapshot as a JSON object (debug / export — not a second source of truth).
    pub fn snapshot(&self) -> Value {
        let map = self.inner.read().expect("state store lock poisoned");
        Value::Object(map.iter().map(|(k, v)| (k.clone(), v.clone())).collect())
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn set_get_remove() {
        let store = StateStore::new();
        store.set("turn", json!(1));
        assert_eq!(store.get("turn"), Some(json!(1)));
        assert!(store.contains("turn"));
        assert_eq!(store.remove("turn"), Some(json!(1)));
        assert!(!store.contains("turn"));
    }

    #[test]
    fn keys_sorted_and_clear() {
        let store = StateStore::new();
        store.set("b", json!("y"));
        store.set("a", json!("x"));
        assert_eq!(store.keys(), vec!["a", "b"]);
        store.clear();
        assert!(store.is_empty());
    }
}
