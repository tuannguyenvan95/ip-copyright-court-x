# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }
from genlayer import *
from dataclasses import dataclass
import json

# Compatibility guard: Ensure gl.UserError is available across GenVM and gltest direct environments
if not hasattr(gl, "UserError"):
    try:
        gl.UserError = gl.vm.UserError
    except Exception:
        pass


def _addr_str(addr: Address) -> str:
    """Safely format an Address instance into a lowercase hex string."""
    try:
        return addr.as_hex.lower()
    except Exception:
        return str(addr).lower()


def _get_sender() -> Address:
    """Safely obtain transaction sender across GenVM runtime versions."""
    try:
        return gl.message.sender
    except Exception:
        try:
            return gl.message.sender_address
        except Exception:
            raise gl.UserError("Cannot resolve sender address.")


def _safe_transfer(recipient: Address, amount: bigint) -> None:
    """Safely disburse native GEN to an address using official GenLayer SDK pattern."""
    if amount <= bigint(0):
        return
    gl.get_contract_at(recipient).emit_transfer(value=u256(int(amount)))


def _parse_url_host_and_path(raw_url: str) -> tuple[str, str]:
    """Parse raw URL into validated canonical host and clean path."""
    clean = raw_url.strip()
    if "?" in clean:
        clean = clean.split("?")[0]
    if "#" in clean:
        clean = clean.split("#")[0]
    clean = clean.strip()

    if clean.startswith("https://"):
        rest = clean[8:]
    elif clean.startswith("http://"):
        rest = clean[7:]
    else:
        raise gl.UserError("URL must begin with http:// or https://")

    parts = rest.split("/", 1)
    host = parts[0].strip().lower()
    path = parts[1].strip() if len(parts) > 1 else ""

    if host not in ("github.com", "www.github.com", "raw.githubusercontent.com"):
        raise gl.UserError(f"Host must be github.com or raw.githubusercontent.com, got: {host}")

    return host, path


def _parse_canonical_repo(repo_url: str) -> tuple[str, str]:
    """Extract and validate canonical owner and repository name from URL."""
    _, path = _parse_url_host_and_path(repo_url)
    segments = [s.strip() for s in path.strip("/").split("/") if s.strip()]
    if len(segments) < 2:
        raise gl.UserError("Invalid repository URL format. Expected: https://github.com/<owner>/<repo>")

    owner = segments[0].lower()
    repo = segments[1].lower()
    if repo.endswith(".git"):
        repo = repo[:-4]

    if not owner or not repo:
        raise gl.UserError("Repository owner and name must not be empty.")

    return owner, repo


@allow_storage
@dataclass
class InfringementDispute:
    dispute_id: str
    complainant: Address
    original_repo_url: str      # Source repository containing original license/copyright
    accused_repo_url: str       # Accused repository alleged to be infringing
    license_type: str           # e.g., "MIT", "GPL-3.0", "APACHE-2.0"
    original_code_file_url: str # Raw link to original file
    accused_code_file_url: str  # Raw link to accused copycat file
    dispute_bond: bigint        # Staked bond by complainant
    status: str                 # "FILED", "ADJUDICATED", "DISMISSED"
    verdict: str                # "PENDING", "PROVEN_INFRINGEMENT", "LEGITIMATE_FAIR_USE", "INSUFFICIENT_EVIDENCE"
    reason: str                 # Consensus explanation
    deadline: bigint            # Expiration timestamp
    created_at: bigint
    resolved_at: bigint


class Contract(gl.Contract):
    """
    IPCopyrightCourtX: Autonomous Open Source License & Code Infringement Court
    Track: Onchain Justice / Autonomous Protocols
    """
    owner: Address
    dispute_count: bigint
    disputes: TreeMap[str, InfringementDispute]
    blacklisted_repos: TreeMap[str, bool]
    min_dispute_bond: bigint

    def __init__(self):
        # GenVM automatically initializes TreeMap storage fields to empty.
        self.owner = _get_sender()
        self.dispute_count = bigint(0)
        self.min_dispute_bond = bigint(1000)

    def _get_current_timestamp(self) -> bigint:
        """Derive trusted deterministic execution timestamp from GenLayer transaction context."""
        try:
            from datetime import datetime
            dt_raw = getattr(gl.message, "datetime", None)
            if dt_raw is None and hasattr(gl, "message_raw") and isinstance(gl.message_raw, dict):
                dt_raw = gl.message_raw.get("datetime")
            if dt_raw:
                dt_str = str(dt_raw).strip().replace("Z", "+00:00")
                dt = datetime.fromisoformat(dt_str)
                ts = int(dt.timestamp())
                if ts > 0:
                    return bigint(ts)
        except Exception:
            pass

        try:
            if hasattr(gl, "block") and hasattr(gl.block, "timestamp"):
                ts = int(gl.block.timestamp)
                if ts > 0:
                    return bigint(ts)
        except Exception:
            pass

        return bigint(0)

    def _parse_llm_json(self, text: str) -> dict:
        """Safely parse LLM responses, stripping markdown wrappers if present."""
        try:
            cleaned = str(text).strip()
            if cleaned.startswith("```json"):
                cleaned = cleaned[7:]
            elif cleaned.startswith("```"):
                cleaned = cleaned[3:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
            return json.loads(cleaned.strip())
        except Exception as e:
            return {
                "verdict": "INSUFFICIENT_EVIDENCE",
                "confidence": 0,
                "reason": f"Failed to parse LLM JSON: {str(e)[:100]}"
            }

    @gl.public.write.payable
    def file_dispute(
        self,
        original_repo_url: str,
        accused_repo_url: str,
        license_type: str,
        original_code_file_url: str,
        accused_code_file_url: str,
        challenge_duration_sec: int
    ) -> str:
        """
        Original creator files an infringement claim against an accused repository, locking a dispute bond.
        """
        bond = bigint(gl.message.value)
        if bond < self.min_dispute_bond:
            raise gl.UserError(f"Dispute bond must be at least {self.min_dispute_bond} wei.")

        orig_owner, orig_repo = _parse_canonical_repo(original_repo_url)
        acc_owner, acc_repo = _parse_canonical_repo(accused_repo_url)

        canonical_orig = f"https://github.com/{orig_owner}/{orig_repo}"
        canonical_acc = f"https://github.com/{acc_owner}/{acc_repo}"

        if canonical_orig == canonical_acc:
            raise gl.UserError("Original and accused repositories cannot be identical.")

        clean_license = license_type.strip().upper()
        if len(clean_license) < 3:
            raise gl.UserError("License type is too short (e.g., MIT, GPL-3.0, APACHE-2.0).")

        clean_orig_file = original_code_file_url.strip()
        clean_acc_file = accused_code_file_url.strip()

        if not (clean_orig_file.startswith("http://") or clean_orig_file.startswith("https://")):
            raise gl.UserError("original_code_file_url must begin with http:// or https://")
        if not (clean_acc_file.startswith("http://") or clean_acc_file.startswith("https://")):
            raise gl.UserError("accused_code_file_url must begin with http:// or https://")

        # Canonical Binding: verify file URLs correspond to configured repos
        if f"{orig_owner}/{orig_repo}".lower() not in clean_orig_file.lower():
            raise gl.UserError("original_code_file_url does not belong to original repository.")
        if f"{acc_owner}/{acc_repo}".lower() not in clean_acc_file.lower():
            raise gl.UserError("accused_code_file_url does not belong to accused repository.")

        now_ts = self._get_current_timestamp()
        duration = bigint(challenge_duration_sec if challenge_duration_sec >= 86400 else 86400)
        deadline = now_ts + duration if now_ts > bigint(0) else bigint(86400 * 7)

        self.dispute_count += bigint(1)
        did = str(self.dispute_count)

        self.disputes[did] = InfringementDispute(
            dispute_id=did,
            complainant=_get_sender(),
            original_repo_url=canonical_orig,
            accused_repo_url=canonical_acc,
            license_type=clean_license,
            original_code_file_url=clean_orig_file,
            accused_code_file_url=clean_acc_file,
            dispute_bond=bond,
            status="FILED",
            verdict="PENDING",
            reason="Infringement dispute registered. Awaiting autonomous AI adjudication.",
            deadline=deadline,
            created_at=self.dispute_count,
            resolved_at=bigint(0)
        )

        return did

    @gl.public.write
    def adjudicate_dispute(self, dispute_id: str) -> None:
        """
        Validators inspect both code files, evaluate code identity, copyright notices, and license adherence,
        then reach 100% discrete consensus on infringement.
        """
        if dispute_id not in self.disputes:
            raise gl.UserError("Dispute not found.")

        dispute = self.disputes[dispute_id]
        if dispute.status != "FILED":
            raise gl.UserError("Dispute is already resolved or dismissed.")

        orig_url_local = str(dispute.original_code_file_url)
        acc_url_local = str(dispute.accused_code_file_url)
        lic_local = str(dispute.license_type)
        acc_repo_local = str(dispute.accused_repo_url)

        def leader_fn():
            # 1. Fetch original code snippet
            orig_code = ""
            try:
                res_orig = gl.nondet.web.render(orig_url_local, mode="text")
                orig_code = res_orig.content if hasattr(res_orig, "content") else str(res_orig)
            except Exception:
                orig_code = ""

            # 2. Fetch accused code snippet
            acc_code = ""
            try:
                res_acc = gl.nondet.web.render(acc_url_local, mode="text")
                acc_code = res_acc.content if hasattr(res_acc, "content") else str(res_acc)
            except Exception:
                acc_code = ""

            if len(orig_code.strip()) < 20 or len(acc_code.strip()) < 20:
                return {
                    "verdict": "INSUFFICIENT_EVIDENCE",
                    "confidence": 100,
                    "reason": "One or both code source files are offline, 404, or blank."
                }

            snippet_orig = orig_code[:3500]
            snippet_acc = acc_code[:3500]

            prompt = f"""You are an Objective Open-Source Intellectual Property & License Arbiter on GenLayer.
Evaluate whether the Accused Code impermissibly copies the Original Code in breach of open-source license standards.

DECLARED LICENSE: {lic_local}
ACCUSED REPOSITORY: {acc_repo_local}

ORIGINAL CODE:
\"\"\"
{snippet_orig}
\"\"\"

ACCUSED CODE:
\"\"\"
{snippet_acc}
\"\"\"

LEGAL ARBITRATION RUBRIC:
Classify into strictly ONE of the following discrete verdicts:
- "PROVEN_INFRINGEMENT": Substantial structural, algorithmic, or verbatim code duplication exists where copyright headers were stripped, license notices removed, or license constraints (such as copyleft reciprocity) breached.
- "LEGITIMATE_FAIR_USE": Normal use of generic standard library APIs, independent clean-room re-implementation, or properly attributed usage complying with the license terms.
- "INSUFFICIENT_EVIDENCE": The two files are fundamentally distinct, insufficient code overlap exists, or context is ambiguous.

OUTPUT FORMAT:
Respond ONLY with a VALID JSON object (no markdown, no backticks):
{{
  "verdict": "PROVEN_INFRINGEMENT" | "LEGITIMATE_FAIR_USE" | "INSUFFICIENT_EVIDENCE",
  "confidence": <integer from 0 to 100>,
  "reason": "<concise explanation max 220 characters>"
}}"""

            try:
                raw_res = gl.nondet.exec_prompt(prompt, response_format="json")
                parsed = None
                if isinstance(raw_res, dict):
                    parsed = raw_res
                elif hasattr(raw_res, "content") and isinstance(raw_res.content, dict):
                    parsed = raw_res.content
                else:
                    text = raw_res.content if hasattr(raw_res, "content") else str(raw_res)
                    cleaned = str(text).strip()
                    if cleaned.startswith("```json"):
                        cleaned = cleaned[7:]
                    elif cleaned.startswith("```"):
                        cleaned = cleaned[3:]
                    if cleaned.endswith("```"):
                        cleaned = cleaned[:-3]
                    parsed = json.loads(cleaned.strip())

                verdict_candidate = str(parsed.get("verdict", "INSUFFICIENT_EVIDENCE")).strip().upper()
                valid_verdicts = ("PROVEN_INFRINGEMENT", "LEGITIMATE_FAIR_USE", "INSUFFICIENT_EVIDENCE")
                if verdict_candidate not in valid_verdicts:
                    verdict_candidate = "INSUFFICIENT_EVIDENCE"

                try:
                    conf = int(parsed.get("confidence", 0))
                    conf = max(0, min(100, conf))
                except Exception:
                    conf = 50

                reason_str = str(parsed.get("reason", "IP evaluated by autonomous AI jury."))[:220]

                return {
                    "verdict": verdict_candidate,
                    "confidence": conf,
                    "reason": reason_str
                }
            except Exception as e:
                return {
                    "verdict": "INSUFFICIENT_EVIDENCE",
                    "confidence": 0,
                    "reason": f"Evaluation error: {str(e)[:100]}"
                }

        def validator_fn(leader_res) -> bool:
            if not isinstance(leader_res, gl.vm.Return):
                return False
            leader = leader_res.calldata
            if not isinstance(leader, dict) or "verdict" not in leader:
                return False

            valid_verdicts = ("PROVEN_INFRINGEMENT", "LEGITIMATE_FAIR_USE", "INSUFFICIENT_EVIDENCE")
            l_verdict = str(leader.get("verdict", "")).strip().upper()
            if l_verdict not in valid_verdicts:
                return False

            mine = leader_fn()
            m_verdict = str(mine.get("verdict", "")).strip().upper()

            # DISCRETE EQUIVALENCE: 100% agreement on exact discrete IP verdict
            return l_verdict == m_verdict

        adjudication_res = gl.vm.run_nondet(leader_fn, validator_fn)
        if isinstance(adjudication_res, dict):
            final_res = adjudication_res
        else:
            final_res = self._parse_llm_json(str(adjudication_res))

        verdict = str(final_res.get("verdict", "INSUFFICIENT_EVIDENCE")).strip().upper()
        valid_verdicts = ("PROVEN_INFRINGEMENT", "LEGITIMATE_FAIR_USE", "INSUFFICIENT_EVIDENCE")
        if verdict not in valid_verdicts:
            verdict = "INSUFFICIENT_EVIDENCE"

        reason = str(final_res.get("reason", "Consensus concluded."))

        dispute.status = "ADJUDICATED"
        dispute.verdict = verdict
        dispute.reason = reason
        dispute.resolved_at = self.dispute_count

        bond_val = dispute.dispute_bond

        if verdict == "PROVEN_INFRINGEMENT":
            # Blacklist the infringing repo on-chain permanently
            self.blacklisted_repos[dispute.accused_repo_url.lower()] = True
            self.disputes[dispute_id] = dispute
            # Refund bond back to complainant (claim proven true)
            if bond_val > bigint(0):
                _safe_transfer(dispute.complainant, bond_val)

        elif verdict == "LEGITIMATE_FAIR_USE":
            # Accused was innocent: bond is forfeited to court pool
            self.disputes[dispute_id] = dispute

        else:
            # INSUFFICIENT_EVIDENCE: refund bond to complainant
            self.disputes[dispute_id] = dispute
            if bond_val > bigint(0):
                _safe_transfer(dispute.complainant, bond_val)

    @gl.public.write
    def cancel_expired_dispute(self, dispute_id: str) -> None:
        """
        Safe Recovery Path: If dispute exceeds deadline without adjudication, complainant can dismiss and recover bond.
        """
        if dispute_id not in self.disputes:
            raise gl.UserError("Dispute not found.")

        dispute = self.disputes[dispute_id]
        if _addr_str(_get_sender()) != _addr_str(dispute.complainant):
            raise gl.UserError("Only complainant can cancel expired dispute.")

        if dispute.status != "FILED":
            raise gl.UserError("Dispute is already adjudicated or dismissed.")

        now_ts = self._get_current_timestamp()
        if now_ts > bigint(0) and now_ts <= dispute.deadline:
            raise gl.UserError("Dispute deadline has not passed yet.")

        bond_val = dispute.dispute_bond
        dispute.status = "DISMISSED"
        dispute.verdict = "INSUFFICIENT_EVIDENCE"
        dispute.reason = "Dispute lapsed past deadline and was dismissed by complainant."
        dispute.resolved_at = self.dispute_count
        self.disputes[dispute_id] = dispute

        if bond_val > bigint(0):
            _safe_transfer(dispute.complainant, bond_val)

    @gl.public.view
    def is_repo_blacklisted(self, repo_url: str) -> bool:
        """Check if an accused repository has been confirmed as an infringing copycat on-chain."""
        clean_url = repo_url.strip().lower()
        return clean_url in self.blacklisted_repos and self.blacklisted_repos[clean_url]

    @gl.public.view
    def get_dispute(self, dispute_id: str) -> str:
        """Retrieve details of an IP dispute as a JSON string."""
        if dispute_id not in self.disputes:
            raise gl.UserError("Dispute not found.")
        d = self.disputes[dispute_id]
        return json.dumps({
            "dispute_id": d.dispute_id,
            "complainant": _addr_str(d.complainant),
            "original_repo": d.original_repo_url,
            "accused_repo": d.accused_repo_url,
            "license_type": d.license_type,
            "original_file": d.original_code_file_url,
            "accused_file": d.accused_code_file_url,
            "dispute_bond": str(d.dispute_bond),
            "status": d.status,
            "verdict": d.verdict,
            "reason": d.reason,
            "deadline": str(d.deadline),
            "created_at": str(d.created_at),
            "resolved_at": str(d.resolved_at)
        })

    @gl.public.view
    def get_current_time(self) -> int:
        """Retrieve current contract execution timestamp."""
        return int(str(self._get_current_timestamp()))

    @gl.public.view
    def get_dispute_count(self) -> int:
        return int(self.dispute_count)

    @gl.public.view
    def get_owner(self) -> str:
        return _addr_str(self.owner)
