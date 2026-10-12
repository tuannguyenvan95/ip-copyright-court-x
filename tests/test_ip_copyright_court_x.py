import pytest
import json
from gltest import *


def _to_hex(addr) -> str:
    """Helper to convert test address to lowercase hex."""
    if hasattr(addr, "as_hex"):
        return addr.as_hex.lower()
    if isinstance(addr, bytes):
        return "0x" + addr.hex().lower()
    return str(addr).lower()


def setup_post_message_hook(direct_vm):
    """Intercept cross-contract calls / emit_transfer to track recipient balances in tests."""
    def post_message_hook(vm, request):
        if "PostMessage" in request:
            pm = request["PostMessage"]
            dest_addr = pm["address"]
            value = int(pm.get("value", 0))
            dest_bytes = vm._to_bytes(dest_addr)
            vm._balances[dest_bytes] = vm._balances.get(dest_bytes, 0) + value
            return {"ok": None}
        if "EthSend" in request:
            es = request["EthSend"]
            dest_addr = es.get("to") or es.get("address") or es.get("recipient")
            value = int(es.get("value", 0))
            dest_bytes = vm._to_bytes(dest_addr)
            vm._balances[dest_bytes] = vm._balances.get(dest_bytes, 0) + value
            return {"ok": None}
        return None

    direct_vm._gl_call_hook = post_message_hook


@pytest.fixture
def contract(direct_deploy):
    return direct_deploy("contracts/ip_copyright_court_x.py")


def test_initial_state(contract, direct_vm, direct_alice):
    """Verify clean initial state on contract deployment."""
    assert contract.get_dispute_count() == 0
    assert contract.get_owner() == _to_hex(direct_vm.sender)


def test_file_dispute_success_canonical_paths(contract, direct_vm, direct_alice):
    """
    Test creator filing an infringement dispute.
    Validates canonical GitHub repositories, constructs authoritative raw URLs automatically,
    and binds relative file paths on-chain without trusting caller license strings.
    """
    direct_vm.sender = direct_alice
    direct_vm.value = 1500

    orig_repo = "https://github.com/alice-dev/cryptolib"
    acc_repo = "https://github.com/bob-copycat/cryptolib-fork"

    did = contract.file_dispute(
        original_repo_url=orig_repo,
        accused_repo_url=acc_repo,
        original_code_file_path="src/cipher.py",
        accused_code_file_path="src/cipher.py",
        original_ref="main",
        accused_ref="main",
        challenge_duration_sec=86400 * 3
    )
    assert str(did) == "1"
    assert contract.get_dispute_count() == 1

    d_json = json.loads(contract.get_dispute("1"))
    assert d_json["dispute_id"] == "1"
    assert d_json["complainant"] == _to_hex(direct_alice)
    assert d_json["original_repo"] == "https://github.com/alice-dev/cryptolib"
    assert d_json["accused_repo"] == "https://github.com/bob-copycat/cryptolib-fork"
    assert d_json["canonical_orig_file_url"] == "https://raw.githubusercontent.com/alice-dev/cryptolib/main/src/cipher.py"
    assert d_json["canonical_acc_file_url"] == "https://raw.githubusercontent.com/bob-copycat/cryptolib-fork/main/src/cipher.py"
    assert d_json["dispute_bond"] == "1500"
    assert d_json["status"] == "FILED"
    assert d_json["verdict"] == "PENDING"
    assert d_json["verified_original_license"] == "PENDING_VERIFICATION"
    assert contract.is_repo_blacklisted("https://github.com/bob-copycat/cryptolib-fork") is False


def test_file_dispute_validation_errors(contract, direct_vm, direct_alice):
    """Test comprehensive input and bond validation constraints."""
    direct_vm.sender = direct_alice

    # 1. Bond below min_dispute_bond (1000)
    direct_vm.value = 500
    with pytest.raises(Exception) as exc:
        contract.file_dispute(
            original_repo_url="https://github.com/alice-dev/cryptolib",
            accused_repo_url="https://github.com/bob-copycat/cryptolib-fork",
            original_code_file_path="cipher.py",
            accused_code_file_path="cipher.py",
            original_ref="main",
            accused_ref="main",
            challenge_duration_sec=86400
        )
    assert "Dispute bond must be at least 1000 wei" in str(exc.value)

    # 2. Identical repositories
    direct_vm.value = 1000
    with pytest.raises(Exception) as exc:
        contract.file_dispute(
            original_repo_url="https://github.com/alice-dev/cryptolib",
            accused_repo_url="https://github.com/alice-dev/cryptolib",
            original_code_file_path="cipher.py",
            accused_code_file_path="cipher.py",
            original_ref="main",
            accused_ref="main",
            challenge_duration_sec=86400
        )
    assert "Original and accused repositories cannot be identical" in str(exc.value)

    # 3. Path traversal attack in file path
    with pytest.raises(Exception) as exc:
        contract.file_dispute(
            original_repo_url="https://github.com/alice-dev/cryptolib",
            accused_repo_url="https://github.com/bob-copycat/cryptolib-fork",
            original_code_file_path="../etc/passwd",
            accused_code_file_path="cipher.py",
            original_ref="main",
            accused_ref="main",
            challenge_duration_sec=86400
        )
    assert "Invalid relative path components" in str(exc.value)

    # 4. Host not authoritative github.com
    with pytest.raises(Exception) as exc:
        contract.file_dispute(
            original_repo_url="https://gitlab.com/alice-dev/cryptolib",
            accused_repo_url="https://github.com/bob-copycat/cryptolib-fork",
            original_code_file_path="cipher.py",
            accused_code_file_path="cipher.py",
            original_ref="main",
            accused_ref="main",
            challenge_duration_sec=86400
        )
    assert "Host must be authoritative github.com" in str(exc.value)


def test_adjudicate_proven_infringement_independent_license_verification(contract, direct_vm, direct_alice):
    """
    Consensus Outcome 1: PROVEN_INFRINGEMENT
    Validators independently acquire:
      - Original repository's verified LICENSE file (GPL-3.0)
      - Accused repository's lack of LICENSE file or stripped headers
      - AST analysis of code duplication
    Result: Infringing repo blacklisted on-chain, complainant bond refunded, verified licenses saved.
    """
    setup_post_message_hook(direct_vm)

    direct_vm.sender = direct_alice
    direct_vm.value = 2000

    did = contract.file_dispute(
        original_repo_url="https://github.com/alice-dev/secure-math",
        accused_repo_url="https://github.com/stealer-dev/secure-math-clone",
        original_code_file_path="math.py",
        accused_code_file_path="math.py",
        original_ref="main",
        accused_ref="main",
        challenge_duration_sec=86400 * 5
    )

    orig_lic = "GNU GENERAL PUBLIC LICENSE Version 3, 29 June 2007. Copyright (C) 2025 Alice Nakamoto."
    code_alice = "'''Copyright (C) Alice - GPL-3.0'''\ndef compute_curve_points(a, b):\n    return [x**2 + a*x + b for x in range(100)]\n"
    code_stealer = "# Proprietary closed logic - All rights reserved\ndef compute_curve_points(a, b):\n    return [x**2 + a*x + b for x in range(100)]\n"

    # Mocks for independent evidence acquisition
    direct_vm.mock_web(".*alice-dev/secure-math/main/LICENSE.*", {"status": 200, "body": orig_lic})
    direct_vm.mock_web(".*stealer-dev/secure-math-clone/main/LICENSE.*", {"status": 404, "body": "404 Not Found"})
    direct_vm.mock_web(".*alice-dev/secure-math/main/math.py.*", {"status": 200, "body": code_alice})
    direct_vm.mock_web(".*stealer-dev/secure-math-clone/main/math.py.*", {"status": 200, "body": code_stealer})

    direct_vm.mock_llm(".*", json.dumps({
        "verdict": "PROVEN_INFRINGEMENT",
        "verified_orig_license": "GPL-3.0",
        "verified_acc_license": "NONE_STRIPPED",
        "confidence": 99,
        "reason": "Direct code copy with license header stripped and GPL-3.0 deleted. Closed-source re-licensing violates copyleft reciprocity."
    }))

    contract.adjudicate_dispute(did)

    d_json = json.loads(contract.get_dispute(did))
    assert d_json["status"] == "ADJUDICATED"
    assert d_json["verdict"] == "PROVEN_INFRINGEMENT"
    assert d_json["verified_original_license"] == "GPL-3.0"
    assert d_json["verified_accused_license"] == "NONE_STRIPPED"
    assert "Direct code copy" in d_json["reason"]

    # Accused repo is blacklisted
    assert contract.is_repo_blacklisted("https://github.com/stealer-dev/secure-math-clone") is True

    # Complainant bond refunded
    alice_bytes = direct_vm._to_bytes(direct_alice)
    assert direct_vm._balances.get(alice_bytes, 0) == 2000


def test_adjudicate_legitimate_fair_use_forfeits_bond(contract, direct_vm, direct_alice):
    """
    Consensus Outcome 2: LEGITIMATE_FAIR_USE
    Validators inspect both repos: accused developed clean-room code and has independent MIT license.
    Result: Accused exonerated, complainant bond forfeited to court.
    """
    setup_post_message_hook(direct_vm)

    direct_vm.sender = direct_alice
    direct_vm.value = 1500

    did = contract.file_dispute(
        original_repo_url="https://github.com/alice-dev/utils",
        accused_repo_url="https://github.com/bob-clean/utils",
        original_code_file_path="helper.py",
        accused_code_file_path="helper.py",
        original_ref="main",
        accused_ref="main",
        challenge_duration_sec=86400 * 5
    )

    orig_lic = "MIT License. Copyright (c) 2024 Alice."
    acc_lic = "MIT License. Copyright (c) 2025 Bob Clean."
    code_alice = "import os\ndef get_env(k):\n    return os.environ.get(k, None)\n"
    code_bob = "import os\ndef fetch_var(name):\n    return os.getenv(name)\n"

    direct_vm.mock_web(".*alice-dev/utils/main/LICENSE.*", {"status": 200, "body": orig_lic})
    direct_vm.mock_web(".*bob-clean/utils/main/LICENSE.*", {"status": 200, "body": acc_lic})
    direct_vm.mock_web(".*alice-dev/utils/main/helper.py.*", {"status": 200, "body": code_alice})
    direct_vm.mock_web(".*bob-clean/utils/main/helper.py.*", {"status": 200, "body": code_bob})

    direct_vm.mock_llm(".*", json.dumps({
        "verdict": "LEGITIMATE_FAIR_USE",
        "verified_orig_license": "MIT",
        "verified_acc_license": "MIT",
        "confidence": 95,
        "reason": "Independent clean-room re-implementation using standard library APIs. Proper MIT attribution preserved."
    }))

    contract.adjudicate_dispute(did)

    d_json = json.loads(contract.get_dispute(did))
    assert d_json["status"] == "ADJUDICATED"
    assert d_json["verdict"] == "LEGITIMATE_FAIR_USE"
    assert d_json["verified_original_license"] == "MIT"
    assert d_json["verified_accused_license"] == "MIT"

    # Accused repo NOT blacklisted
    assert contract.is_repo_blacklisted("https://github.com/bob-clean/utils") is False

    # Complainant bond is NOT refunded (forfeited)
    alice_bytes = direct_vm._to_bytes(direct_alice)
    assert direct_vm._balances.get(alice_bytes, 0) == 0


def test_adjudicate_original_lacks_license_file(contract, direct_vm, direct_alice):
    """
    Provenance Guard:
    If original repository does not possess a verified open-source LICENSE file on GitHub,
    validators conclude INSUFFICIENT_EVIDENCE due to lack of verified license terms.
    """
    setup_post_message_hook(direct_vm)

    direct_vm.sender = direct_alice
    direct_vm.value = 1200

    did = contract.file_dispute(
        original_repo_url="https://github.com/alice-dev/unlicensed-repo",
        accused_repo_url="https://github.com/other-dev/repo-b",
        original_code_file_path="code.py",
        accused_code_file_path="code.py",
        original_ref="main",
        accused_ref="main",
        challenge_duration_sec=86400 * 2
    )

    # Original repo has no LICENSE file (404)
    direct_vm.mock_web(".*alice-dev/unlicensed-repo/main/LICENSE.*", {"status": 404, "body": "404 Not Found"})
    direct_vm.mock_web(".*alice-dev/unlicensed-repo/main/code.py.*", {"status": 200, "body": "def foo(): return 42\n" * 10})
    direct_vm.mock_web(".*other-dev/repo-b/main/code.py.*", {"status": 200, "body": "def bar(): return 42\n" * 10})

    contract.adjudicate_dispute(did)

    d_json = json.loads(contract.get_dispute(did))
    assert d_json["status"] == "ADJUDICATED"
    assert d_json["verdict"] == "INSUFFICIENT_EVIDENCE"
    assert "no verifiable LICENSE file" in d_json["reason"]
    assert d_json["verified_original_license"] == "NO_LICENSE_FOUND"

    # Complainant bond refunded safely
    alice_bytes = direct_vm._to_bytes(direct_alice)
    assert direct_vm._balances.get(alice_bytes, 0) == 1200


def test_double_adjudication_prevention(contract, direct_vm, direct_alice):
    """Cannot adjudicate an already resolved dispute."""
    direct_vm.sender = direct_alice
    direct_vm.value = 1000

    did = contract.file_dispute(
        original_repo_url="https://github.com/alice-dev/lib1",
        accused_repo_url="https://github.com/bob-dev/lib1",
        original_code_file_path="lib.py",
        accused_code_file_path="lib.py",
        original_ref="main",
        accused_ref="main",
        challenge_duration_sec=86400
    )

    orig_lic = "MIT License (c) Alice"
    direct_vm.mock_web(".*alice-dev/lib1/main/LICENSE.*", {"status": 200, "body": orig_lic})
    direct_vm.mock_web(".*bob-dev/lib1/main/LICENSE.*", {"status": 404, "body": "404"})
    direct_vm.mock_web(".*alice-dev/lib1/main/lib.py.*", {"status": 200, "body": "x = 1\n" * 20})
    direct_vm.mock_web(".*bob-dev/lib1/main/lib.py.*", {"status": 200, "body": "y = 2\n" * 20})
    direct_vm.mock_llm(".*", json.dumps({
        "verdict": "INSUFFICIENT_EVIDENCE",
        "verified_orig_license": "MIT",
        "verified_acc_license": "NONE",
        "confidence": 90,
        "reason": "No match."
    }))

    contract.adjudicate_dispute(did)

    with pytest.raises(Exception) as exc:
        contract.adjudicate_dispute(did)
    assert "Dispute is already resolved or dismissed" in str(exc.value)


def test_cancel_expired_dispute_recovery_path(contract, direct_vm, direct_alice, direct_bob):
    """
    Safe Recovery Path: If dispute passes deadline without adjudication, complainant can recover bond.
    """
    setup_post_message_hook(direct_vm)

    direct_vm.sender = direct_alice
    direct_vm.value = 3000

    did = contract.file_dispute(
        original_repo_url="https://github.com/alice-dev/unadjudicated-repo",
        accused_repo_url="https://github.com/troll-dev/copycat-repo",
        original_code_file_path="code.py",
        accused_code_file_path="code.py",
        original_ref="main",
        accused_ref="main",
        challenge_duration_sec=86400
    )

    d_json = json.loads(contract.get_dispute(did))
    deadline = int(d_json["deadline"])

    # 1. Non-complainant cannot cancel
    direct_vm.sender = direct_bob
    with pytest.raises(Exception) as exc:
        contract.cancel_expired_dispute(did)
    assert "Only complainant can cancel expired dispute" in str(exc.value)

    # 2. Cannot cancel before deadline
    direct_vm.warp("2026-06-01T10:00:00Z")
    direct_vm.sender = direct_alice
    direct_vm.value = 3000
    did2 = contract.file_dispute(
        original_repo_url="https://github.com/alice-dev/unadjudicated-repo-2",
        accused_repo_url="https://github.com/troll-dev/copycat-repo-2",
        original_code_file_path="code.py",
        accused_code_file_path="code.py",
        original_ref="main",
        accused_ref="main",
        challenge_duration_sec=86400
    )
    d_json2 = json.loads(contract.get_dispute(did2))
    deadline2 = int(d_json2["deadline"])

    with pytest.raises(Exception) as exc:
        contract.cancel_expired_dispute(did2)
    assert "Dispute deadline has not passed yet" in str(exc.value)

    # Warp past deadline (2 days forward)
    direct_vm.warp("2026-06-03T10:00:00Z")
    assert contract.get_current_time() > deadline2

    direct_vm.sender = direct_alice
    contract.cancel_expired_dispute(did2)

    d_json_after = json.loads(contract.get_dispute(did2))
    assert d_json_after["status"] == "DISMISSED"
    assert "Dispute lapsed past deadline" in d_json_after["reason"]

    alice_bytes = direct_vm._to_bytes(direct_alice)
    assert direct_vm._balances.get(alice_bytes, 0) == 3000


def test_dispute_not_found_queries(contract, direct_alice, direct_vm):
    """Querying or adjudicating non-existent dispute raises UserError."""
    with pytest.raises(Exception) as exc:
        contract.get_dispute("9999")
    assert "Dispute not found" in str(exc.value)

    with pytest.raises(Exception) as exc:
        contract.adjudicate_dispute("9999")
    assert "Dispute not found" in str(exc.value)

    direct_vm.sender = direct_alice
    with pytest.raises(Exception) as exc:
        contract.cancel_expired_dispute("9999")
    assert "Dispute not found" in str(exc.value)


def test_invalid_url_protocol(contract, direct_alice, direct_vm):
    """URLs without http or https raise UserError."""
    direct_vm.sender = direct_alice
    direct_vm.value = 1500
    with pytest.raises(Exception) as exc:
        contract.file_dispute(
            original_repo_url="ftp://github.com/alice/repo",
            accused_repo_url="https://github.com/bob/repo",
            original_code_file_path="code.py",
            accused_code_file_path="code.py",
            original_ref="main",
            accused_ref="main",
            challenge_duration_sec=86400
        )
    assert "URL must begin with http:// or https://" in str(exc.value)
