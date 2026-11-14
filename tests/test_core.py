from documind.documents import split_text
from documind.extraction import extract_fields_locally

def test_split_text_produces_multiple_chunks():
    chunks = split_text('A sentence for testing. ' * 100, chunk_size=240, overlap=30)
    assert len(chunks) > 1
    assert all(chunks)

def test_invoice_fields_are_extracted():
    text = 'Invoice Number: INV-1001\nInvoice Date: 05-09-2026\nCustomer Name: ABC Technologies\nTax Amount: 1500\nTotal Amount: 10000'
    result = extract_fields_locally(text, ['InvoiceNumber', 'InvoiceDate', 'CustomerName', 'TaxAmount', 'TotalAmount'])
    assert result['InvoiceNumber']['value'] == 'INV-1001'
    assert result['InvoiceDate']['value'] == '05-09-2026'
    assert result['CustomerName']['value'] == 'ABC Technologies'
    assert result['TaxAmount']['value'] == '1500'
    assert result['TotalAmount']['value'] == '10000'
