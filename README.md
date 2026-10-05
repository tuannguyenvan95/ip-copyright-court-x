# IPCopyrightCourtX — Autonomous Open Source License & Code Infringement Court

> **Track:** Onchain Justice / Autonomous Protocols  
> **Target Environment:** [GenLayer Studio](https://studio.genlayer.com)  
> **Network:** GenLayer `studionet` (Chain ID: `61999` / `0xF1EF`)  
> **Contract Source:** [`contracts/ip_copyright_court_x.py`](contracts/ip_copyright_court_x.py)  
> **Execution Engine:** GenVM / Optimistic Democracy Subjective Consensus  
> **Package / SDK:** `py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6`  
> **Test Suite:** 10 unit tests passing (`gltest` / `pytest`)

---

## 1. Abstract & Problem Statement

Open-source creators and maintainers consistently face illegal intellectual property poaching: bad actors clone repositories, strip copyright notices and open-source licenses (MIT, GPL-3.0, Apache-2.0), obscure variable names, and monetize the code without reciprocity or attribution.

Traditional legal arbitration:
- Costs tens of thousands of dollars in attorney fees.
- Takes years in traditional judicial court systems.
- Fails cross-border jurisdictional enforcement against pseudonymous developers.

**IPCopyrightCourtX** solves this via GenLayer:
1. **On-Chain Copyright Staking**: Original creators file an infringement challenge backed by a refundable challenge bond (`min_dispute_bond = 1000 wei`).
2. **Autonomous Evidence Scraping**: GenLayer validators fetch live source code and license headers directly from GitHub using `gl.nondet.web.render`.
3. **AST & Semantic LLM Consensus**: Validators run LLM-powered AST and copyright analysis to detect stripped headers, copyleft breaches, or blatant code plagiarism.
4. **100% Discrete Consensus**: Validators enforce strict agreement across discrete legal outcomes (`PROVEN_INFRINGEMENT`, `LEGITIMATE_FAIR_USE`, `INSUFFICIENT_EVIDENCE`).
5. **Decentralized Enforcement**:
   - `PROVEN_INFRINGEMENT`: Infringing repo is permanently blacklisted on-chain (`blacklisted_repos`), and complainant's bond is returned.
   - `LEGITIMATE_FAIR_USE`: Accused is exonerated, and frivolous claim bond is forfeited.
   - `INSUFFICIENT_EVIDENCE`: Complainant bond refunded safely.
6. **Safe Recovery Path**: Complainant can cancel and reclaim their bond if adjudication lapses past the challenge deadline.

---

## 2. Core Architectural Pillars

### 1. Line 1 Dependency Pragma
Begins directly with `# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }`, guaranteeing exact build dependency resolution in GenVM without version mismatch.

### 2. Canonical GitHub Binding & URL Anti-Spoofing
- Verifies hosts are strictly `github.com` or `raw.githubusercontent.com`.
- Extracts canonical `<owner>/<repo>` identifiers.
- Validates that code file URLs canonically correspond to the declared repository to prevent cross-repo replay exploits.
- Rejects identical repository claims (`orig_repo == acc_repo`).

### 3. Subjective LLM Jury & Discrete Consensus
Validators inspect both code files up to 3,500 characters, evaluate license reciprocity, and vote. The contract enforces discrete equivalence in `validator_fn`:
```python
def validator_fn(leader_res) -> bool:
    if not isinstance(leader_res, gl.vm.Return):
        return False
    leader = leader_res.calldata
    ...
    # DISCRETE EQUIVALENCE: 100% agreement on exact discrete IP verdict
    return l_verdict == m_verdict
```
Two validators with differing phrasing in `reason` still achieve consensus, while differing verdicts reject the block.

### 4. Economic Determinism & Bond Flow
| Verdict | Repos Blacklisted | Complainant Bond | Legal Meaning |
|---|---|---|---|
| `PROVEN_INFRINGEMENT` | Yes (Accused Repo) | 100% Refunded | Code theft & license stripping confirmed |
| `LEGITIMATE_FAIR_USE` | No | Forfeited to Court | Accused is innocent; independent creation |
| `INSUFFICIENT_EVIDENCE` | No | 100% Refunded | 404/Inaccessible files, or ambiguous overlap |

### 5. Safe Funder / Complainant Recovery Path
If the dispute exceeds the configured deadline without adjudication (`cancel_expired_dispute`), the complainant can dismiss the case and withdraw 100% of their locked bond.

---

## 3. Contract Specification

### Storage Layout
- `owner: Address` — Administrator/deployer address.
- `dispute_count: bigint` — Total disputes registered.
- `disputes: TreeMap[str, InfringementDispute]` — Registry of IP disputes.
- `blacklisted_repos: TreeMap[str, bool]` — Permanent on-chain repository blacklist.
- `min_dispute_bond: bigint` — Minimum bond required (1000 wei).

### Methods

| Method | Type | Access | Description |
|---|---|---|---|
| `file_dispute(...)` | Write, Payable | Anyone (Creator) | Locks bond, validates canonical repos and file bindings, creates dispute. |
| `adjudicate_dispute(dispute_id)` | Write | Anyone (Keeper) | Fetches code via `web.render`, executes LLM consensus jury, executes settlement & blacklist. |
| `cancel_expired_dispute(dispute_id)` | Write | Complainant only | Safe bond recovery if deadline has passed. |
| `is_repo_blacklisted(repo_url)` | View | Public | Checks whether a GitHub repo is confirmed as an infringing copycat on-chain. |
| `get_dispute(dispute_id)` | View | Public | Returns complete dispute details as JSON string. |
| `get_dispute_count()` | View | Public | Returns total count of disputes filed. |
| `get_current_time()` | View | Public | Derives deterministic GenVM block/message timestamp. |
| `get_owner()` | View | Public | Returns contract owner address. |

---

## 4. End-to-End Walkthrough

### Step 1: File Infringement Dispute
- Complainant Alice calls `file_dispute`:
  - `original_repo_url`: `https://github.com/alice-dev/cryptolib`
  - `accused_repo_url`: `https://github.com/bob-copycat/cryptolib-fork`
  - `license_type`: `MIT`
  - `original_code_file_url`: `https://raw.githubusercontent.com/alice-dev/cryptolib/main/cipher.py`
  - `accused_code_file_url`: `https://raw.githubusercontent.com/bob-copycat/cryptolib-fork/main/cipher.py`
  - `challenge_duration_sec`: `259200` (3 days)
  - `value`: `1500 wei`

### Step 2: Autonomous Adjudication
- Anyone invokes `adjudicate_dispute("1")`:
  1. GenLayer validator fetches code via `gl.nondet.web.render`.
  2. AST and semantic similarity evaluated against license rules via `gl.nondet.exec_prompt`.
  3. Validators reach consensus on `PROVEN_INFRINGEMENT`.
  4. Contract updates state:
     - `verdict = "PROVEN_INFRINGEMENT"`
     - `blacklisted_repos["https://github.com/bob-copycat/cryptolib-fork"] = True`
     - Bond (1500 wei) is transferred back to Alice.

### Step 3: Verification
- External protocols or package managers query `is_repo_blacklisted("https://github.com/bob-copycat/cryptolib-fork")` -> Returns `True`.

---

## 5. Testing & Verification

Run the comprehensive unit test suite:

```bash
# Run pytest with gltest
pytest -v
```

### Test Coverage Highlights:
- ✅ `test_initial_state`: Clean initialization and owner assignment.
- ✅ `test_file_dispute_success`: Proper bond locking and dispute creation.
- ✅ `test_file_dispute_validation_errors`: Strict validation of bonds, licenses, URL hosts, and repository containment.
- ✅ `test_adjudicate_proven_infringement_blacklists_and_refunds`: Infringement verdict, on-chain blacklist, and bond refund.
- ✅ `test_adjudicate_legitimate_fair_use_forfeits_bond`: Fair use outcome, exoneration, and bond forfeiture.
- ✅ `test_adjudicate_insufficient_evidence_refunds_bond`: Inaccessible files/ambiguity, bond refund.
- ✅ `test_double_adjudication_prevention`: Protection against re-executing resolved disputes.
- ✅ `test_cancel_expired_dispute_recovery_path`: Safe bond recovery post-deadline.
- ✅ `test_dispute_not_found_queries`: Error handling for non-existent cases.
- ✅ `test_invalid_url_protocol`: Protocol verification constraints.

---

## 6. Deployment on GenLayer Studionet

1. Open [GenLayer Studio](https://studio.genlayer.com).
2. Create a new contract file: `ip_copyright_court_x.py`.
3. Copy the contract code from [`contracts/ip_copyright_court_x.py`](contracts/ip_copyright_court_x.py).
4. Deploy the contract using the Studio Deploy button on `studionet`.
5. Interact with `file_dispute`, `adjudicate_dispute`, and `is_repo_blacklisted` directly via the Studio UI or `genlayer-js`.
