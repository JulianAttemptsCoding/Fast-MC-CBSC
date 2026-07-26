import pytest
import torch

from cbsc_zdc.models.graph import EdgeMessageBlock


def test_edge_message_block_changes_destination_and_rejects_invalid_edges():
    torch.manual_seed(2)
    block = EdgeMessageBlock(hidden=8, edge_dim=3, edge_chunk_size=1).eval()
    h = torch.randn(2, 3, 8)
    edge_index = torch.tensor([[0, 1], [1, 2]])
    edge_features = torch.randn(2, 3)
    with torch.no_grad():
        out = block(h, edge_index, edge_features)
    assert out.shape == h.shape
    assert not torch.allclose(out, h)

    bad = torch.tensor([[0], [3]])
    with pytest.raises(ValueError, match="invalid node id"):
        block(h, bad, torch.randn(1, 3))


def test_edge_message_block_rejects_bad_shapes():
    block = EdgeMessageBlock(hidden=8, edge_dim=3)
    h = torch.randn(1, 3, 8)
    with torch.no_grad():
        empty_out = block(
            h,
            torch.empty(2, 0, dtype=torch.long),
            torch.empty(0, 3),
        )
    assert empty_out.shape == h.shape
    with pytest.raises(ValueError, match="shape"):
        block(h, torch.tensor([0, 1]), torch.randn(1, 3))
    with pytest.raises(ValueError, match="feature"):
        block(h, torch.tensor([[0], [1]]), torch.randn(1, 2))
