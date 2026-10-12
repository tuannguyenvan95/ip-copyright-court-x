# IPCopyrightCourtX — Autonomous Open Source License & Code Infringement Court

> **Track:** Onchain Justice / Autonomous Protocols  
> **Target Environment:** [GenLayer Studio](https://studio.genlayer.com)  
> **Network:** GenLayer `studionet` (Chain ID: `61999` / `0xF1EF`)  
> **Contract Address:** `0xaA35C7D86cf02F4f9A409f1d5B9F594835a501c6`  
> **Contract Source:** [`contracts/ip_copyright_court_x.py`](contracts/ip_copyright_court_x.py)  
> **Execution Engine:** GenVM / Optimistic Democracy Subjective Consensus  
> **Package / SDK:** `py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6`  
> **Test Suite:** 10 unit tests passing (`gltest` / `pytest`)

---

## 1. Deployment & Live Network Evidence

The `IPCopyrightCourtX` Intelligent Contract is deployed on GenLayer `studionet`:

- **Contract Address:** `0xaA35C7D86cf02F4f9A409f1d5B9F594835a501c6`
- **Network:** `studionet` (Chain ID: `61999` / `0xF1EF`)
- **Explorer:** [https://explorer.genlayer.com/address/0xaA35C7D86cf02F4f9A409f1d5B9F594835a501c6](https://explorer.genlayer.com/address/0xaA35C7D86cf02F4f9A409f1d5B9F594835a501c6)
- **Studio Explorer:** [https://explorer-studio.genlayer.com/address/0xaA35C7D86cf02F4f9A409f1d5B9F594835a501c6](https://explorer-studio.genlayer.com/address/0xaA35C7D86cf02F4f9A409f1d5B9F594835a501c6)
- **Contract Source:** [`contracts/ip_copyright_court_x.py`](contracts/ip_copyright_court_x.py)

---

## 2. Project Overview & Architectural Highlights

Open-source creators and maintainers consistently face illegal intellectual property poaching: bad actors clone repositories, strip copyright notices and open-source licenses (MIT, GPL-3.0, Apache-2.0), obscure variable names, and monetize the code without reciprocity or attribution.

Traditional legal arbitration:
- Costs tens of thousands of dollars in attorney fees.
- Takes years in traditional judicial court systems.
- Fails cross-border jurisdictional enforcement against pseudonymous developers.

**IPCopyrightCourtX** solves this via GenLayer:
1. **On-Chain Copyright Staking**: Original creators file an infringement challenge backed by a refundable challenge bond (`min_dispute_bond = 1000 wei`).
2. **Independent Evidence Acquisition**: GenLayer validators independently fetch official `LICENSE`/`LICENSE.md` files from both original and accused repositories, directly acquiring and binding true license facts on-chain rather than relying on caller declarations.
3. **Canonical GitHub Path Construction**: File URLs are strictly generated from authoritative GitHub coordinates (`https://raw.githubusercontent.com/<owner>/<repo>/<ref>/<path>`), preventing URL spoofing and path traversal (`../`) attacks.
4. **AST, License Reciprocity, & Authorship Provenance Consensus**: Validators run LLM-powered AST and copyright analysis to detect stripped headers, copyleft breaches, or blatant code plagiarism.
5. **100% Discrete Consensus**: Validators enforce strict agreement across discrete legal outcomes (`PROVEN_INFRINGEMENT`, `LEGITIMATE_FAIR_USE`, `INSUFFICIENT_EVIDENCE`).
6. **Decentralized Enforcement**:
   - `PROVEN_INFRINGEMENT`: Infringing repo is permanently blacklisted on-chain (`blacklisted_repos`), and complainant's bond is returned.
   - `LEGITIMATE_FAIR_USE`: Accused is exonerated, and frivolous claim bond is forfeited to the court pool.
   - `INSUFFICIENT_EVIDENCE`: Complainant bond refunded safely (e.g., if original repository lacks a verifiable LICENSE file or files are inaccessible).
7. **Safe Recovery Path**: Complainant can cancel and reclaim their bond if adjudication lapses past the challenge deadline (`cancel_expired_dispute`).

---

## 3. Core Architectural Pillars

### 1. Line 1 Dependency Pragma
Begins directly with `# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }`, guaranteeing exact build dependency resolution in GenVM without version mismatch.

### 2. Independent On-Chain License Acquisition & Fact-Binding
Instead of trusting caller-submitted license strings:
- The contract independently scrapes `LICENSE` and `LICENSE.md` from the original repository.
- If the original repository has no verifiable license, the dispute concludes with `INSUFFICIENT_EVIDENCE` (lack of legal standing).
- The contract independently checks the accused repository for stripped license files or unauthorized proprietary re-licensing.
- Discovered licenses are permanently bound into on-chain state (`verified_original_license`, `verified_accused_license`).

### 3. Canonical GitHub Binding & Path Sanitization
- Validates that repository URLs belong strictly to `github.com`.
- Normalizes relative file paths, blocking traversal attacks (`..`).
- Contract programmatically derives authoritative raw URLs:
  `https://raw.githubusercontent.com/{owner}/{repo}/{ref}/{clean_path}`.

### 4. Subjective LLM Jury & Discrete Consensus
Validators inspect both code files up to 3,000 characters along with both license files up to 1,500 characters, evaluate license reciprocity and AST overlap, and vote:
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

### 5. Economic Determinism & Bond Flow
| Verdict | Repos Blacklisted | Complainant Bond | Legal Meaning |
|---|---|---|---|
| `PROVEN_INFRINGEMENT` | Yes (Accused Repo) | 100% Refunded | Code theft & license stripping confirmed |
| `LEGITIMATE_FAIR_USE` | No | Forfeited to Court | Accused is innocent; independent creation |
| `INSUFFICIENT_EVIDENCE` | No | 100% Refunded | Original lacks LICENSE, 404 files, or negligible overlap |

### 6. Safe Complainant Recovery Path
If the dispute exceeds the configured deadline without adjudication (`cancel_expired_dispute`), the complainant can dismiss the case and withdraw 100% of their locked bond.

---

## 4. Contract Specification

### Storage Layout
- `owner: Address` — Administrator/deployer address.
- `dispute_count: bigint` — Total disputes registered.
- `disputes: TreeMap[str, InfringementDispute]` — Registry of IP disputes.
- `blacklisted_repos: TreeMap[str, bool]` — Permanent on-chain repository blacklist.
- `min_dispute_bond: bigint` — Minimum bond required (1000 wei).

### Methods

| Method | Type | Access | Description |
|---|---|---|---|
| `file_dispute(...)` | Write, Payable | Anyone (Creator) | Locks bond, validates canonical repos, constructs authoritative paths, creates dispute. |
| `adjudicate_dispute(dispute_id)` | Write | Anyone (Keeper) | Independently fetches licenses and code from GitHub, executes LLM jury consensus, updates blacklist & bond. |
| `cancel_expired_dispute(dispute_id)` | Write | Complainant only | Safe bond recovery if deadline has passed without adjudication. |
| `is_repo_blacklisted(repo_url)` | View | Public | Checks whether a GitHub repo is confirmed as an infringing copycat on-chain. |
| `get_dispute(dispute_id)` | View | Public | Returns complete dispute details with verified licenses as JSON string. |
| `get_dispute_count()` | View | Public | Returns total count of disputes filed. |
| `get_current_time()` | View | Public | Derives deterministic GenVM block/message timestamp. |
| `get_owner()` | View | Public | Returns contract owner address. |

---

## 5. End-to-End Walkthrough

### Step 1: File Infringement Dispute
- Complainant Alice calls `file_dispute`:
  - `original_repo_url`: `https://github.com/alice-dev/cryptolib`
  - `accused_repo_url`: `https://github.com/bob-copycat/cryptolib-fork`
  - `original_code_file_path`: `src/cipher.py`
  - `accused_code_file_path`: `src/cipher.py`
  - `original_ref`: `main`
  - `accused_ref`: `main`
  - `challenge_duration_sec`: `259200` (3 days)
  - `value`: `1500 wei`

### Step 2: Autonomous Adjudication
- Anyone invokes `adjudicate_dispute("1")`:
  1. GenLayer validators independently fetch `LICENSE` from `alice-dev/cryptolib` (identifies GPL-3.0).
  2. GenLayer validators independently fetch `LICENSE` from `bob-copycat/cryptolib-fork` (finds no license / stripped).
  3. GenLayer validators fetch canonical raw files for `src/cipher.py`.
  4. AST and semantic similarity evaluated against license rules via `gl.nondet.exec_prompt`.
  5. Validators reach discrete consensus on `PROVEN_INFRINGEMENT`.
  6. Contract updates state:
     - `verdict = "PROVEN_INFRINGEMENT"`
     - `verified_original_license = "GPL-3.0"`
     - `verified_accused_license = "NONE_STRIPPED"`
     - `blacklisted_repos["https://github.com/bob-copycat/cryptolib-fork"] = True`
     - Bond (1500 wei) is transferred back to Alice.

### Step 3: Verification
- External protocols or package managers query `is_repo_blacklisted("https://github.com/bob-copycat/cryptolib-fork")` -> Returns `True`.

---

## 6. Testing & Verification

Run the comprehensive unit test suite:

```bash
# Run pytest with gltest
pytest -v
```

### Test Coverage Highlights:
- ✅ `test_initial_state`: Clean initialization and owner assignment.
- ✅ `test_file_dispute_success_canonical_paths`: Canonical path construction and dispute creation without trusting caller declarations.
- ✅ `test_file_dispute_validation_errors`: Strict validation of bonds, URL hosts, and directory traversal blocks.
- ✅ `test_adjudicate_proven_infringement_independent_license_verification`: Independent license detection, infringement verdict, blacklist, and bond refund.
- ✅ `test_adjudicate_legitimate_fair_use_forfeits_bond`: Fair use outcome, independent MIT attribution, and bond forfeiture.
- ✅ `test_adjudicate_original_lacks_license_file`: Provenance guard verifying original repo has valid license before finding infringement.
- ✅ `test_double_adjudication_prevention`: Protection against re-executing resolved disputes.
- ✅ `test_cancel_expired_dispute_recovery_path`: Safe bond recovery post-deadline.
- ✅ `test_dispute_not_found_queries`: Error handling for non-existent cases.
- ✅ `test_invalid_url_protocol`: Protocol verification constraints.

---

## 7. Deployment on GenLayer Studionet

1. Open [GenLayer Studio](https://studio.genlayer.com).
2. Create a new contract file: `ip_copyright_court_x.py`.
3. Copy the contract code from [`contracts/ip_copyright_court_x.py`](contracts/ip_copyright_court_x.py).
4. Deploy the contract using the Studio Deploy button on `studionet`.
5. Interact with `file_dispute`, `adjudicate_dispute`, and `is_repo_blacklisted` directly via the Studio UI or `genlayer-js`.
