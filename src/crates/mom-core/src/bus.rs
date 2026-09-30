//! Hop bus — carry payloads between graph nodes without models owning the format.
//!
//! Default transport is text/JSON (plug-and-play across vendors). Other transports
//! (e.g. embedding bytes) plug in behind the same encode/decode API.

use std::sync::Arc;

use serde_json::Value;

/// How a payload is encoded on the wire / in memory between hops.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub enum PayloadKind {
    /// UTF-8 JSON text — default, vendor-agnostic.
    TextJson,
    /// Packed little-endian `f32` embedding vector.
    Embedding,
}

impl PayloadKind {
    /// Stable string id for bindings / logs.
    pub fn as_str(self) -> &'static str {
        match self {
            Self::TextJson => "text_json",
            Self::Embedding => "embedding",
        }
    }
}

/// Opaque hop payload produced by a [`Transport`].
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Payload {
    kind: PayloadKind,
    body: Vec<u8>,
}

impl Payload {
    /// Construct a payload (used by transports).
    pub fn new(kind: PayloadKind, body: Vec<u8>) -> Self {
        Self { kind, body }
    }

    /// Encoding kind.
    pub fn kind(&self) -> PayloadKind {
        self.kind
    }

    /// Raw bytes (JSON UTF-8 for text; f32 LE for embeddings).
    pub fn body(&self) -> &[u8] {
        &self.body
    }

    /// Body as UTF-8 (text transports).
    pub fn as_text(&self) -> Result<&str, BusError> {
        std::str::from_utf8(&self.body).map_err(|_| BusError::InvalidUtf8)
    }
}

/// Transport encode/decode failure.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum BusError {
    /// Payload kind does not match the active transport.
    KindMismatch {
        /// Kind the transport expected.
        expected: PayloadKind,
        /// Kind on the payload.
        got: PayloadKind,
    },
    /// JSON serialize/deserialize failed.
    Json(String),
    /// Body was not valid UTF-8.
    InvalidUtf8,
    /// Embedding encode expected a JSON array of numbers.
    ExpectedNumberArray,
    /// Embedding decode body length not divisible by 4.
    BadEmbeddingLength,
}

impl std::fmt::Display for BusError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Self::KindMismatch { expected, got } => write!(
                f,
                "payload kind mismatch: expected {}, got {}",
                expected.as_str(),
                got.as_str()
            ),
            Self::Json(msg) => write!(f, "json error: {msg}"),
            Self::InvalidUtf8 => write!(f, "payload body is not valid UTF-8"),
            Self::ExpectedNumberArray => {
                write!(f, "embedding transport expects a JSON array of numbers")
            }
            Self::BadEmbeddingLength => {
                write!(f, "embedding body length must be a multiple of 4")
            }
        }
    }
}

impl std::error::Error for BusError {}

/// Pluggable hop encoding. Implement this to add a new bus without touching the runtime.
pub trait Transport: Send + Sync {
    /// Kind this transport reads and writes.
    fn kind(&self) -> PayloadKind;

    /// Encode a JSON value into a hop payload.
    fn encode(&self, value: &Value) -> Result<Payload, BusError>;

    /// Decode a hop payload back into a JSON value.
    fn decode(&self, payload: &Payload) -> Result<Value, BusError>;
}

/// Default transport: serde JSON as UTF-8 text.
#[derive(Debug, Default, Clone, Copy)]
pub struct TextJsonTransport;

impl Transport for TextJsonTransport {
    fn kind(&self) -> PayloadKind {
        PayloadKind::TextJson
    }

    fn encode(&self, value: &Value) -> Result<Payload, BusError> {
        let body = serde_json::to_vec(value).map_err(|e| BusError::Json(e.to_string()))?;
        Ok(Payload::new(PayloadKind::TextJson, body))
    }

    fn decode(&self, payload: &Payload) -> Result<Value, BusError> {
        if payload.kind() != PayloadKind::TextJson {
            return Err(BusError::KindMismatch {
                expected: PayloadKind::TextJson,
                got: payload.kind(),
            });
        }
        serde_json::from_slice(payload.body()).map_err(|e| BusError::Json(e.to_string()))
    }
}

/// Optional embedding transport: JSON number arrays ↔ little-endian `f32` bytes.
///
/// Not required for plug-and-play text models; proves the bus is swappable.
#[derive(Debug, Default, Clone, Copy)]
pub struct EmbeddingTransport;

impl Transport for EmbeddingTransport {
    fn kind(&self) -> PayloadKind {
        PayloadKind::Embedding
    }

    fn encode(&self, value: &Value) -> Result<Payload, BusError> {
        let Some(arr) = value.as_array() else {
            return Err(BusError::ExpectedNumberArray);
        };
        let mut body = Vec::with_capacity(arr.len() * 4);
        for item in arr {
            let Some(n) = item.as_f64() else {
                return Err(BusError::ExpectedNumberArray);
            };
            body.extend_from_slice(&(n as f32).to_le_bytes());
        }
        Ok(Payload::new(PayloadKind::Embedding, body))
    }

    fn decode(&self, payload: &Payload) -> Result<Value, BusError> {
        if payload.kind() != PayloadKind::Embedding {
            return Err(BusError::KindMismatch {
                expected: PayloadKind::Embedding,
                got: payload.kind(),
            });
        }
        let body = payload.body();
        if body.len() % 4 != 0 {
            return Err(BusError::BadEmbeddingLength);
        }
        let mut out = Vec::with_capacity(body.len() / 4);
        for chunk in body.chunks_exact(4) {
            let n = f32::from_le_bytes([chunk[0], chunk[1], chunk[2], chunk[3]]);
            out.push(Value::from(n as f64));
        }
        Ok(Value::Array(out))
    }
}

/// Hop bus: one active [`Transport`], encode/decode for inter-node payloads.
#[derive(Clone)]
pub struct Bus {
    transport: Arc<dyn Transport>,
}

impl std::fmt::Debug for Bus {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.debug_struct("Bus")
            .field("kind", &self.kind().as_str())
            .finish()
    }
}

impl Default for Bus {
    fn default() -> Self {
        Self::text_json()
    }
}

impl Bus {
    /// Text/JSON bus (v1 default).
    pub fn text_json() -> Self {
        Self::with_transport(Arc::new(TextJsonTransport))
    }

    /// Embedding bus (optional alternate transport).
    pub fn embedding() -> Self {
        Self::with_transport(Arc::new(EmbeddingTransport))
    }

    /// Plug in any transport.
    pub fn with_transport(transport: Arc<dyn Transport>) -> Self {
        Self { transport }
    }

    /// Active payload kind.
    pub fn kind(&self) -> PayloadKind {
        self.transport.kind()
    }

    /// Encode a value for the next hop.
    pub fn encode(&self, value: &Value) -> Result<Payload, BusError> {
        self.transport.encode(value)
    }

    /// Decode a hop payload into a value.
    pub fn decode(&self, payload: &Payload) -> Result<Value, BusError> {
        self.transport.decode(payload)
    }

    /// Encode then decode (sanity / tests).
    pub fn roundtrip(&self, value: &Value) -> Result<Value, BusError> {
        let payload = self.encode(value)?;
        self.decode(&payload)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn text_json_roundtrip() {
        let bus = Bus::text_json();
        let v = json!({"role": "user", "text": "hi"});
        assert_eq!(bus.roundtrip(&v).unwrap(), v);
        let payload = bus.encode(&v).unwrap();
        assert_eq!(payload.kind(), PayloadKind::TextJson);
        assert!(payload.as_text().unwrap().contains("hi"));
    }

    #[test]
    fn embedding_roundtrip() {
        let bus = Bus::embedding();
        let v = json!([0.0, 1.5, -2.0]);
        let back = bus.roundtrip(&v).unwrap();
        let arr = back.as_array().unwrap();
        assert_eq!(arr.len(), 3);
        assert!((arr[1].as_f64().unwrap() - 1.5).abs() < 1e-6);
    }

    #[test]
    fn kind_mismatch() {
        let text = Bus::text_json();
        let emb = Bus::embedding();
        let payload = emb.encode(&json!([1.0])).unwrap();
        assert!(matches!(
            text.decode(&payload),
            Err(BusError::KindMismatch { .. })
        ));
    }
}
