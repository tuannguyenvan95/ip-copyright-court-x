# Sample Infringement Dispute Scenario

This directory demonstrates sample inputs and code snippets for evaluating copyright infringement claims in `IPCopyrightCourtX`.

## Case 1: Egregious Copyleft Stripping (PROVEN_INFRINGEMENT)

### Original Repository & File
- **Original Repo:** `https://github.com/alice-dev/zk-crypto-core`
- **License:** `GPL-3.0`
- **File URL:** `https://raw.githubusercontent.com/alice-dev/zk-crypto-core/main/pairing.py`
- **Snippet:**
```python
"""
Copyright (C) 2025 Alice Nakamoto - GPL-3.0 License
Recursive SNARK curve pairing operations.
"""

def compute_miller_loop(p, q, curve_order):
    f = 1
    for bit in bin(curve_order)[3:]:
        f = (f * f) % curve_order
        if bit == '1':
            f = (f * p * q) % curve_order
    return f
```

### Accused Repository & File
- **Accused Repo:** `https://github.com/stealer-corp/closed-enterprise-zk`
- **License Stripping:** License removed, changed to proprietary copyright notice.
- **File URL:** `https://raw.githubusercontent.com/stealer-corp/closed-enterprise-zk/main/pairing.py`
- **Snippet:**
```python
"""
(c) 2026 Stealer Corporation - All Rights Reserved. Confidential.
"""

def compute_miller_loop(p, q, curve_order):
    f = 1
    for bit in bin(curve_order)[3:]:
        f = (f * f) % curve_order
        if bit == '1':
            f = (f * p * q) % curve_order
    return f
```

### Expected Adjudication Result:
- **Verdict:** `PROVEN_INFRINGEMENT`
- **Confidence:** `98`
- **Action:** Complainant bond refunded, `stealer-corp/closed-enterprise-zk` permanently added to on-chain blacklist.
