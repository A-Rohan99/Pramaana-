import pytest
from unittest.mock import MagicMock, patch
from pipeline import extract_invoice_items_llm, sync_invoice_to_inventory


def test_extract_invoice_items_llm_no_api_key():
    """Verify that extract_invoice_items_llm returns empty list if no API key is set."""
    with patch.dict("os.environ", {"GEMINI_API_KEY": ""}):
        res = extract_invoice_items_llm("test invoice text")
        assert res == []


@patch("google.genai.Client")
def test_extract_invoice_items_llm_success(mock_client_class):
    """Verify that extract_invoice_items_llm successfully parses JSON returned by Gemini client."""
    mock_client = MagicMock()
    mock_client_class.return_value = mock_client
    
    # Mock model generate_content response
    mock_part = MagicMock()
    mock_part.text = '[{"item_name": "Sugar", "quantity": 10.5, "unit_price": 40.0, "unit": "kg"}]'
    
    mock_content = MagicMock()
    mock_content.parts = [mock_part]
    
    mock_candidate = MagicMock()
    mock_candidate.content = mock_content
    
    mock_response = MagicMock()
    mock_response.candidates = [mock_candidate]
    
    mock_client.models.generate_content.return_value = mock_response

    with patch.dict("os.environ", {"GEMINI_API_KEY": "fake_key_here"}):
        res = extract_invoice_items_llm("some invoice details")
        assert len(res) == 1
        assert res[0]["item_name"] == "Sugar"
        assert res[0]["quantity"] == 10.5
        assert res[0]["unit_price"] == 40.0
        assert res[0]["unit"] == "kg"


@patch("db.get_inventory")
@patch("db.add_or_update_inventory_item")
def test_sync_invoice_to_inventory_new_item(mock_add_update, mock_get_inventory):
    """Verify that sync_invoice_to_inventory inserts new items that do not exist in inventory."""
    mock_get_inventory.return_value = [] # Empty inventory initially
    
    items = [
        {"item_name": "Moong Dal", "quantity": 15.0, "unit_price": 110.0, "unit": "kg"}
    ]
    
    logs = sync_invoice_to_inventory(items)
    
    # Assert get_inventory was called
    mock_get_inventory.assert_called_once()
    
    # Assert add_or_update_inventory_item was called to insert new item
    mock_add_update.assert_called_once_with(
        item_name="Moong Dal",
        quantity=15.0,
        cost_price=110.0,
        unit="kg"
    )
    
    assert len(logs) == 1
    assert "Created new product: Moong Dal" in logs[0]


@patch("db.get_inventory")
@patch("db.add_or_update_inventory_item")
def test_sync_invoice_to_inventory_existing_item(mock_add_update, mock_get_inventory):
    """Verify that sync_invoice_to_inventory adjusts stock for existing items."""
    mock_get_inventory.return_value = [
        {"id": 1, "item_name": "Moong Dal", "quantity": 50.0, "cost_price": 100.0, "unit": "kg"}
    ]
    
    items = [
        {"item_name": "Moong Dal", "quantity": 15.0, "unit_price": 110.0, "unit": "kg"}
    ]
    
    logs = sync_invoice_to_inventory(items)
    
    # Assert get_inventory was called
    mock_get_inventory.assert_called_once()
    
    # Assert add_or_update_inventory_item was called with accumulated quantity (50.0 + 15.0 = 65.0)
    mock_add_update.assert_called_once_with(
        item_name="Moong Dal",
        quantity=65.0,
        cost_price=110.0,
        unit="kg"
    )
    
    assert len(logs) == 1
    assert "Restocked 15.0 kg of Moong Dal" in logs[0]
