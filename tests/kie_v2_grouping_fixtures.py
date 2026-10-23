"""Independent synthetic geometry cases; never TV2 gold or Reader output."""

from tests.kie_v2_fixtures import document, evidence, invoice


def narrow_numbers():
    return evidence(
        [
            ("Currency: VND", 0.05, 0.1, 0.3),
            ("Description", 0.05, 0.3, 0.25),
            ("Unit", 0.32, 0.3, 0.06),
            ("Quantity", 0.40, 0.3, 0.14),
            ("Unit price", 0.56, 0.3, 0.18),
            ("Amount", 0.77, 0.3, 0.19),
            ("Service A", 0.05, 0.35, 0.25),
            ("box", 0.32, 0.35, 0.06),
            ("2", 0.52, 0.35, 0.02),
            ("50000", 0.69, 0.35, 0.05),
            ("100000", 0.90, 0.35, 0.06),
        ]
    )


def cases():
    wrapped = invoice()
    fragment = evidence([("continued name", 0.05, 0.405, 0.25)])["blocks"][0]
    fragment.update(block_id="wrapped", reading_order=len(wrapped["blocks"]))
    wrapped["blocks"].append(fragment)
    split = invoice()
    split["blocks"][15]["text"] = "Dịch vụ"
    fragment = evidence([("mẫu", 0.20, 0.38, 0.10)])["blocks"][0]
    fragment.update(block_id="split", reading_order=len(split["blocks"]))
    split["blocks"].append(fragment)
    merged = invoice()
    merged["blocks"][18]["text"] = "50000 100000"
    del merged["blocks"][19]
    for i, b in enumerate(merged["blocks"]):
        b["reading_order"] = i
    return {
        "aligned": invoice(),
        "narrow-right-aligned": narrow_numbers(),
        "wrapped-description": wrapped,
        "split-description": split,
        "merged-numeric-block": merged,
        "missing-unit-column": invoice(unit=False),
        "missing-unit-cell": invoice(
            rows=[["Dịch vụ mẫu", None, "2", "50000", "100000"]]
        ),
        "partial-next-item": invoice(
            rows=[["A", "box", "1", "10", "10"], ["B", None, None, None, None]]
        ),
        "repeated-header": document(
            invoice(),
            evidence(
                [
                    ("Description", 0.05, 0.10),
                    ("Quantity", 0.53, 0.10),
                    ("Amount", 0.84, 0.10),
                    ("Second page", 0.05, 0.15),
                    ("1", 0.53, 0.15),
                    ("100", 0.84, 0.15),
                ],
                prefix="p1",
            ),
        ),
        "multiple-vat": evidence(
            [
                ("Currency: VND", 0.05, 0.10),
                ("Tax rate", 0.05, 0.20),
                ("Taxable amount", 0.40, 0.20),
                ("Tax amount", 0.75, 0.20),
                ("5%", 0.05, 0.25),
                ("100000", 0.40, 0.25),
                ("5000", 0.75, 0.25),
                ("8%", 0.05, 0.30),
                ("200000", 0.40, 0.30),
                ("16000", 0.75, 0.30),
            ]
        ),
        "unheaded": evidence(
            [("Product", 0.05, 0.1), ("2", 0.53, 0.1), ("100", 0.84, 0.1)]
        ),
        "empty": evidence([]),
    }
