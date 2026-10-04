from mom.image import image_path_from, question_from, stash_vision
from mom.state import StateStore


def test_stash_vision_from_dict(tmp_path):
    img = tmp_path / "x.png"
    img.write_bytes(b"\x89PNG\r\n\x1a\n")
    state = StateStore()
    path, q = stash_vision({"image": str(img), "text": "What color?"}, state)
    assert path == img.resolve()
    assert q == "What color?"
    assert state.get("image_path") == str(img.resolve())
    assert question_from("ignored", state) == "What color?"
    assert image_path_from({}, state) == img.resolve()
