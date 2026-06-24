from app.services.data_masking import mask_citation_payloads, mask_sensitive_data


def test_mask_sensitive_data_replaces_common_personal_identifiers():
    text = (
        "Contact Raj at raj@example.com or +91 98765 43210. "
        "PAN ABCDE1234F, Aadhaar 1234 5678 9012, SSN 123-45-6789, "
        "card 4111 1111 1111 1111."
    )

    masked = mask_sensitive_data(text)

    assert "raj@example.com" not in masked
    assert "+91 98765 43210" not in masked
    assert "ABCDE1234F" not in masked
    assert "1234 5678 9012" not in masked
    assert "123-45-6789" not in masked
    assert "4111 1111 1111 1111" not in masked
    assert "[EMAIL]" in masked
    assert "[PHONE]" in masked
    assert "[PAN]" in masked
    assert "[AADHAAR]" in masked
    assert "[SSN]" in masked
    assert "[PAYMENT_CARD]" in masked


def test_mask_sensitive_data_leaves_ordinary_product_text_unchanged():
    text = "Saffron grade A ships in 5 kg packs and has a 24 month shelf life."

    assert mask_sensitive_data(text) == text


def test_mask_citation_payloads_masks_excerpt_only():
    citations = [{"title": "doc.pdf", "source": "blob", "excerpt": "Email test@example.com"}]

    assert mask_citation_payloads(citations) == [
        {"title": "doc.pdf", "source": "blob", "excerpt": "Email [EMAIL]"}
    ]
