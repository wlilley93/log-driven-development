"""Code extraction engine -- identifies potentially vulnerable code for LLM analysis."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from vibeaudit.models import CodeSnippet, VulnClass


@dataclass
class ExtractionResult:
    vuln_class: VulnClass
    snippets: list[CodeSnippet]
    context: dict = field(default_factory=dict)


LANG_MAP: dict[str, str] = {
    ".ts": "typescript",
    ".tsx": "typescript",
    ".js": "javascript",
    ".jsx": "javascript",
    ".py": "python",
    ".go": "go",
    ".java": "java",
    ".rs": "rust",
    ".rb": "ruby",
    ".php": "php",
    ".cs": "csharp",
    ".scala": "scala",
    ".kt": "kotlin",
}

FRAMEWORK_PATTERNS: dict[str, list[str]] = {
    "nextjs": [
        r"from\s+['\"]next",
        r"import.*NextRequest",
        r"export\s+(?:async\s+)?function\s+(?:GET|POST|PUT|DELETE|PATCH)",
    ],
    "fastapi": [r"from\s+fastapi", r"@app\.(?:get|post|put|delete|patch)", r"@router\.(?:get|post|put|delete|patch)"],
    "flask": [r"from\s+flask", r"@app\.route"],
    "django": [r"from\s+django", r"from\s+rest_framework"],
    "express": [r"require\(['\"]express", r"app\.(?:get|post|put|delete|patch)\("],
    "spring": [r"@RestController", r"@RequestMapping", r"@GetMapping", r"@PostMapping"],
    "gin": [r'"github\.com/gin-gonic/gin"', r"gin\.Context"],
    "rails": [r"class\s+\w+Controller\s*<\s*ApplicationController", r"Rails\.application"],
}

# ── Auth check patterns per framework ────────────────────────────────────────

_AUTH_PATTERNS: list[str] = [
    r"getActiveOrganizationId",
    r"getServerSession",
    r"@login_required",
    r"@permission_required",
    r"authenticate",
    r"requireAuth",
    r"isAuthenticated",
    r"verifyToken",
    r"withAuth",
    r"authMiddleware",
    r"checkAuth",
    r"ensureAuthenticated",
    r"protect\(",
    r"Depends\(\s*get_current_user",
    r"request\.user",
    r"CurrentUser",
    r"@jwt_required",
    r"@token_required",
]

# ── Privileged operation patterns ────────────────────────────────────────────

_PRIVILEGE_PATTERNS: list[str] = [
    r"\.delete\s*\(",
    r"\.deleteMany\s*\(",
    r"\.destroy\s*\(",
    r"\.remove\s*\(",
    r"updateSettings",
    r"manageUsers",
    r"createUser",
    r"deleteUser",
    r"\.update\(\s*\{[^}]*role",
    r"admin",
    r"settings",
    r"grant",
    r"revoke",
    r"permission",
]

_ROLE_CHECK_PATTERNS: list[str] = [
    r"\brole\b",
    r"\bADMIN\b",
    r"\bOWNER\b",
    r"\bisAdmin\b",
    r"\bcheckPermission\b",
    r"\brequireRole\b",
    r"\bhas_permission\b",
    r"\buser_is_admin\b",
    r"\brole_required\b",
    r"\b(?:is_staff|is_superuser)\b",
]


class Extractor:
    """Regex-based code extractor that identifies potentially vulnerable snippets."""

    def __init__(self, max_snippet_lines: int = 200) -> None:
        self.max_snippet_lines = max_snippet_lines

    # ── Public API ───────────────────────────────────────────────────────────

    def extract(
        self, file_path: Path, content: str, vuln_class: VulnClass
    ) -> list[ExtractionResult]:
        """Extract code snippets relevant to a vulnerability class."""
        lang = self.detect_language(file_path)
        framework = self.detect_framework(content)
        lines = content.split("\n")

        method = getattr(self, f"_extract_{vuln_class.value}", None)
        if method is None:
            return []

        snippets: list[CodeSnippet] = method(file_path, content, lines, lang, framework)
        if not snippets:
            return []

        route_path = self._infer_route_path(file_path)
        http_method = self._detect_http_method(content, lang)

        return [
            ExtractionResult(
                vuln_class=vuln_class,
                snippets=snippets,
                context={
                    "route_path": route_path,
                    "http_method": http_method,
                    "framework": framework,
                    "language": lang,
                },
            )
        ]

    def detect_language(self, file_path: Path) -> str:
        return LANG_MAP.get(file_path.suffix, "unknown")

    def detect_framework(self, content: str) -> str:
        for fw, patterns in FRAMEWORK_PATTERNS.items():
            for p in patterns:
                if re.search(p, content):
                    return fw
        return "unknown"

    # ── 1. IDOR ──────────────────────────────────────────────────────────────

    def _extract_idor(
        self,
        file_path: Path,
        content: str,
        lines: list[str],
        lang: str,
        framework: str,
    ) -> list[CodeSnippet]:
        snippets: list[CodeSnippet] = []

        id_param_patterns = [
            r"params\.id\b",
            r'params\["id"\]',
            r"params\['id'\]",
            r"params\.(\w+Id)\b",
            r"\bawait\s+params\b",                     # Next.js 15: const { id } = await params
            r"\{\s*\w*[Ii]d\s*\}\s*=\s*(?:await\s+)?params",  # destructured: { id } = params
            r'request\.args\.get\(["\']id["\']\)',
            r"ctx\.params\.",
            r"req\.params\.",
            r"req\.query\.",
            r'c\.Param\(["\']',
            r"@PathVariable",
        ]

        db_lookup_patterns = [
            r"prisma\.\w+\.find(?:First|Unique|Many)",
            r"Model\.objects\.get\(",
            r"\.findOne\(",
            r"\.findUnique\(",
            r"\.findById\(",
            r"db\.query\(",
            r"\.get_object_or_404\(",
            r"repository\.find",
            r"session\.query\(",
        ]

        ownership_patterns = [
            r"organizationId",
            r"orgId",
            r"userId",
            r"user_id",
            r"owner",
            r"createdBy",
            r"created_by",
            r"belongsTo",
            r"ownerId",
            r"owner_id",
            r"auth\.(?:org|user)",
        ]

        for id_pat in id_param_patterns:
            for m in re.finditer(id_pat, content):
                fn_start, fn_end, fn_text = self._extract_function_body(
                    content, m.start(), lines
                )
                if fn_text is None:
                    continue

                has_db = any(re.search(p, fn_text) for p in db_lookup_patterns)
                has_ownership = any(re.search(p, fn_text) for p in ownership_patterns)

                if has_db and not has_ownership:
                    snippets.append(
                        self._snippet(file_path, lines, fn_start, fn_end, lang)
                    )

        return self._dedupe_snippets(snippets)

    # ── 2. Auth Bypass ───────────────────────────────────────────────────────

    def _extract_auth_bypass(
        self,
        file_path: Path,
        content: str,
        lines: list[str],
        lang: str,
        framework: str,
    ) -> list[CodeSnippet]:
        snippets: list[CodeSnippet] = []

        handler_patterns = [
            # Next.js App Router
            r"export\s+(?:async\s+)?function\s+(GET|POST|PUT|DELETE|PATCH)\b",
            # Express / Fastify
            r"(?:router|app)\.\s*(?:get|post|put|delete|patch)\s*\(",
            # Flask
            r"@app\.route\(",
            r"@blueprint\.route\(",
            # FastAPI
            r"@(?:app|router)\.(?:get|post|put|delete|patch)\(",
            # Django
            r"def\s+(?:get|post|put|delete|patch)\s*\(\s*self\s*,\s*request",
        ]

        for hp in handler_patterns:
            for m in re.finditer(hp, content):
                fn_start, fn_end, fn_text = self._extract_function_body(
                    content, m.start(), lines
                )
                if fn_text is None:
                    continue

                has_auth = any(re.search(ap, fn_text) for ap in _AUTH_PATTERNS)
                if not has_auth:
                    snippets.append(
                        self._snippet(file_path, lines, fn_start, fn_end, lang)
                    )

        return self._dedupe_snippets(snippets)

    # ── 3. Mass Assignment ───────────────────────────────────────────────────

    def _extract_mass_assignment(
        self,
        file_path: Path,
        content: str,
        lines: list[str],
        lang: str,
        framework: str,
    ) -> list[CodeSnippet]:
        snippets: list[CodeSnippet] = []

        patterns = [
            # Prisma: create/update with unsanitized body
            r"prisma\.\w+\.(?:create|update|upsert)\s*\(\s*\{\s*data\s*:\s*body\b",
            r"prisma\.\w+\.(?:create|update|upsert)\s*\(\s*\{\s*data\s*:\s*req\.body\b",
            r"prisma\.\w+\.(?:create|update|upsert)\s*\(\s*\{\s*data\s*:\s*request\.json",
            # Spread of body into data
            r"data\s*:\s*\{\s*\.\.\.(?:body|req\.body|request\.body|data)",
            r"\.\.\.req\.body",
            r"\.\.\.request\.body",
            # Python ORM
            r"\*\*request\.json",
            r"\*\*data\b",
            r"Model\.objects\.create\(\s*\*\*data\b",
            r"Model\.objects\.create\(\s*\*\*request\.(?:json|data)",
            # Direct assignment
            r"Object\.assign\s*\(\s*\w+\s*,\s*req\.body\s*\)",
            r"Object\.assign\s*\(\s*\w+\s*,\s*body\s*\)",
            # Sequelize / Mongoose
            r"\.create\(\s*req\.body\s*\)",
            r"\.create\(\s*body\s*\)",
            r"\.updateOne\(\s*\{[^}]*\}\s*,\s*req\.body\s*\)",
        ]

        for pat in patterns:
            for m in re.finditer(pat, content):
                fn_start, fn_end, fn_text = self._extract_function_body(
                    content, m.start(), lines
                )
                if fn_text is None:
                    continue
                snippets.append(
                    self._snippet(file_path, lines, fn_start, fn_end, lang)
                )

        return self._dedupe_snippets(snippets)

    # ── 4. Race Condition ────────────────────────────────────────────────────

    def _extract_race_condition(
        self,
        file_path: Path,
        content: str,
        lines: list[str],
        lang: str,
        framework: str,
    ) -> list[CodeSnippet]:
        snippets: list[CodeSnippet] = []

        read_patterns = [
            r"\.find(?:First|Unique|One|ById)\s*\(",
            r"\.findOne\s*\(",
            r"\.get\s*\(",
            r"SELECT\s+.*\s+FROM",
            r"\.objects\.get\(",
            r"\.objects\.filter\(",
        ]

        write_patterns = [
            r"\.update\s*\(",
            r"\.updateMany\s*\(",
            r"\.delete\s*\(",
            r"\.deleteMany\s*\(",
            r"\.save\s*\(",
            r"UPDATE\s+\w+\s+SET",
            r"DELETE\s+FROM",
        ]

        transaction_patterns = [
            r"\$transaction",
            r"\.transaction\(",
            r"\bBEGIN\b",
            r"\bCOMMIT\b",
            r"serializable",
            r"SERIALIZABLE",
            r"with_for_update",
            r"FOR\s+UPDATE",
            r"@Transactional",
            r"atomic\(",
        ]

        # Find handler functions and check for read-then-write without transaction
        handler_re = re.compile(
            r"(?:export\s+)?(?:async\s+)?function\s+\w+|"
            r"(?:const|let|var)\s+\w+\s*=\s*(?:async\s+)?\(|"
            r"def\s+\w+\s*\(|"
            r"func\s+\w+\s*\(",
            re.MULTILINE,
        )

        for m in handler_re.finditer(content):
            fn_start, fn_end, fn_text = self._extract_function_body(
                content, m.start(), lines
            )
            if fn_text is None:
                continue

            has_read = any(re.search(rp, fn_text) for rp in read_patterns)
            has_write = any(re.search(wp, fn_text) for wp in write_patterns)
            has_transaction = any(
                re.search(tp, fn_text) for tp in transaction_patterns
            )

            if has_read and has_write and not has_transaction:
                # Confirm the read comes before the write
                first_read = None
                first_write = None
                for rp in read_patterns:
                    rm = re.search(rp, fn_text)
                    if rm and (first_read is None or rm.start() < first_read):
                        first_read = rm.start()
                for wp in write_patterns:
                    wm = re.search(wp, fn_text)
                    if wm and (first_write is None or wm.start() < first_write):
                        first_write = wm.start()

                if (
                    first_read is not None
                    and first_write is not None
                    and first_read < first_write
                ):
                    snippets.append(
                        self._snippet(file_path, lines, fn_start, fn_end, lang)
                    )

        return self._dedupe_snippets(snippets)

    # ── 5. Broken Access Control ─────────────────────────────────────────────

    def _extract_broken_access_control(
        self,
        file_path: Path,
        content: str,
        lines: list[str],
        lang: str,
        framework: str,
    ) -> list[CodeSnippet]:
        snippets: list[CodeSnippet] = []

        # Find handlers performing privileged operations
        handler_re = re.compile(
            r"export\s+(?:async\s+)?function\s+(?:GET|POST|PUT|DELETE|PATCH)\b|"
            r"(?:router|app)\.\s*(?:get|post|put|delete|patch)\s*\(|"
            r"@(?:app|router)\.(?:get|post|put|delete|patch)\(|"
            r"@app\.route\(",
            re.MULTILINE,
        )

        for m in handler_re.finditer(content):
            fn_start, fn_end, fn_text = self._extract_function_body(
                content, m.start(), lines
            )
            if fn_text is None:
                continue

            has_privilege_op = any(
                re.search(pp, fn_text, re.IGNORECASE) for pp in _PRIVILEGE_PATTERNS
            )
            has_role_check = any(
                re.search(rp, fn_text) for rp in _ROLE_CHECK_PATTERNS
            )

            if has_privilege_op and not has_role_check:
                snippets.append(
                    self._snippet(file_path, lines, fn_start, fn_end, lang)
                )

        return self._dedupe_snippets(snippets)

    # ── 6. JWT Misconfiguration ──────────────────────────────────────────────

    def _extract_jwt_misconfig(
        self,
        file_path: Path,
        content: str,
        lines: list[str],
        lang: str,
        framework: str,
    ) -> list[CodeSnippet]:
        snippets: list[CodeSnippet] = []

        jwt_call_patterns = [
            r"jwt\.sign\s*\(",
            r"jwt\.verify\s*\(",
            r"jose\.jwtVerify\s*\(",
            r"jose\.SignJWT\(",
            r"jsonwebtoken",
            r"PyJWT",
            r"jwt\.encode\s*\(",
            r"jwt\.decode\s*\(",
        ]

        issue_patterns = [
            r"""algorithm[s]?\s*[:=]\s*['"]\s*none\s*['"]""",
            r"""algorithms\s*[:=]\s*\[\s*['"]\s*none\s*['"]""",
            r"jwt\.sign\s*\([^)]*\)\s*(?!.*expiresIn)",
            # Hardcoded secret strings (quoted string as the key argument)
            r"""jwt\.sign\s*\([^,]+,\s*['"][^'"]{4,}['"]""",
            r"""jwt\.verify\s*\([^,]+,\s*['"][^'"]{4,}['"]""",
            r"""jwt\.encode\s*\([^,]+,\s*['"][^'"]{4,}['"]""",
            r"""jwt\.decode\s*\([^,]+,\s*['"][^'"]{4,}['"]""",
            # No expiration
            r"jwt\.sign\s*\(\s*\{[^}]*\}\s*,\s*[^,]+\s*\)(?!\s*;?\s*//\s*no-expire)",
        ]

        for jcp in jwt_call_patterns:
            for m in re.finditer(jcp, content):
                fn_start, fn_end, fn_text = self._extract_function_body(
                    content, m.start(), lines
                )
                if fn_text is None:
                    continue

                has_issue = any(re.search(ip, fn_text) for ip in issue_patterns)

                # Check for sign without expiresIn in the options
                sign_match = re.search(r"jwt\.sign\s*\(", fn_text)
                if sign_match and "expiresIn" not in fn_text and "exp" not in fn_text:
                    has_issue = True

                if has_issue:
                    snippets.append(
                        self._snippet(file_path, lines, fn_start, fn_end, lang)
                    )

        return self._dedupe_snippets(snippets)

    # ── 7. SSRF ──────────────────────────────────────────────────────────────

    def _extract_ssrf(
        self,
        file_path: Path,
        content: str,
        lines: list[str],
        lang: str,
        framework: str,
    ) -> list[CodeSnippet]:
        snippets: list[CodeSnippet] = []

        http_call_patterns = [
            r"fetch\s*\(",
            r"axios\.(?:get|post|put|delete|patch|request)\s*\(",
            r"axios\s*\(",
            r"requests\.(?:get|post|put|delete|patch)\s*\(",
            r"httpx\.(?:get|post|put|delete|patch|AsyncClient)\s*\(",
            r"http\.Get\s*\(",
            r"http\.Post\s*\(",
            r"urllib\.request\.urlopen\s*\(",
            r"got\s*\(",
            r"node-fetch\s*\(",
            r"HttpClient",
            r"WebClient",
        ]

        # URL is a variable, not a hardcoded literal
        safe_url_patterns = [
            r"""fetch\s*\(\s*['"`]https?://""",
            r"""axios\.\w+\s*\(\s*['"`]https?://""",
            r"""requests\.\w+\s*\(\s*['"`]https?://""",
        ]

        ssrf_guard_patterns = [
            r"(?:validate|check|verify|sanitize)(?:Url|URL|Uri|URI)",
            r"allowlist",
            r"whitelist",
            r"isInternalUrl",
            r"ALLOWED_HOSTS",
            r"ALLOWED_DOMAINS",
            r"ssrf",
        ]

        for hcp in http_call_patterns:
            for m in re.finditer(hcp, content):
                # Get the line containing this match
                line_num = content[:m.start()].count("\n")
                line_text = lines[line_num] if line_num < len(lines) else ""

                # Skip if URL is a hardcoded safe literal
                is_safe_literal = any(
                    re.search(sp, line_text) for sp in safe_url_patterns
                )
                if is_safe_literal:
                    continue

                fn_start, fn_end, fn_text = self._extract_function_body(
                    content, m.start(), lines
                )
                if fn_text is None:
                    continue

                has_guard = any(
                    re.search(gp, fn_text, re.IGNORECASE) for gp in ssrf_guard_patterns
                )
                if not has_guard:
                    snippets.append(
                        self._snippet(file_path, lines, fn_start, fn_end, lang)
                    )

        return self._dedupe_snippets(snippets)

    # ── 8. Path Traversal ────────────────────────────────────────────────────

    def _extract_path_traversal(
        self,
        file_path: Path,
        content: str,
        lines: list[str],
        lang: str,
        framework: str,
    ) -> list[CodeSnippet]:
        snippets: list[CodeSnippet] = []

        file_op_patterns = [
            r"fs\.readFile(?:Sync)?\s*\(",
            r"fs\.createReadStream\s*\(",
            r"fs\.writeFile(?:Sync)?\s*\(",
            r"fs\.readdir(?:Sync)?\s*\(",
            r"fs\.unlink(?:Sync)?\s*\(",
            r"fs\.stat(?:Sync)?\s*\(",
            r"fs\.access(?:Sync)?\s*\(",
            r"\bopen\s*\(",
            r"Path\s*\(",
            r"os\.path\.join\s*\(",
            r"path\.join\s*\(",
            r"path\.resolve\s*\(",
            r"createWriteStream\s*\(",
            r"sendFile\s*\(",
            r"res\.download\s*\(",
        ]

        user_input_patterns = [
            r"params\.",
            r"query\.",
            r"req\.params",
            r"req\.query",
            r"req\.body",
            r"request\.args",
            r"request\.form",
            r"request\.json",
            r"searchParams",
            r"nextUrl\.searchParams",
        ]

        safe_patterns = [
            r"path\.resolve\s*\([^)]*\)\s*\.startsWith\s*\(",
            r"\.startsWith\s*\(\s*(?:baseDir|uploadDir|STORAGE_DIR|UPLOAD_DIR)",
            r"\.includes\s*\(\s*['\"]\.\.['\"]\s*\)",
            r"sanitize(?:Path|Filename)",
            r"path\.normalize",
            r"realpath",
        ]

        for fop in file_op_patterns:
            for m in re.finditer(fop, content):
                fn_start, fn_end, fn_text = self._extract_function_body(
                    content, m.start(), lines
                )
                if fn_text is None:
                    continue

                has_user_input = any(
                    re.search(up, fn_text) for up in user_input_patterns
                )
                has_safe_check = any(
                    re.search(sp, fn_text) for sp in safe_patterns
                )

                if has_user_input and not has_safe_check:
                    snippets.append(
                        self._snippet(file_path, lines, fn_start, fn_end, lang)
                    )

        return self._dedupe_snippets(snippets)

    # ── 9. Crypto Weakness ───────────────────────────────────────────────────

    def _extract_crypto_weakness(
        self,
        file_path: Path,
        content: str,
        lines: list[str],
        lang: str,
        framework: str,
    ) -> list[CodeSnippet]:
        snippets: list[CodeSnippet] = []

        weak_hash_patterns = [
            (r"createHash\s*\(\s*['\"]md5['\"]\s*\)", "md5_hash"),
            (r"createHash\s*\(\s*['\"]sha1['\"]\s*\)", "sha1_hash"),
            (r"hashlib\.md5\s*\(", "md5_hash"),
            (r"hashlib\.sha1\s*\(", "sha1_hash"),
            (r"Digest::MD5", "md5_hash"),
            (r"Digest::SHA1", "sha1_hash"),
            (r"MessageDigest\.getInstance\s*\(\s*['\"]MD5['\"]\s*\)", "md5_hash"),
            (r"MessageDigest\.getInstance\s*\(\s*['\"]SHA-1['\"]\s*\)", "sha1_hash"),
        ]

        password_context_patterns = [
            r"password",
            r"passwd",
            r"secret",
            r"credential",
            r"auth",
        ]

        # Random for security-sensitive context
        insecure_random_patterns = [
            (r"Math\.random\s*\(\s*\)", "math_random"),
            (r"random\.random\s*\(\s*\)", "py_random"),
            (r"random\.randint\s*\(", "py_random"),
            (r"rand\(\)", "generic_random"),
        ]

        security_context_patterns = [
            r"token",
            r"secret",
            r"key",
            r"nonce",
            r"salt",
            r"csrf",
            r"session",
            r"otp",
            r"code",
            r"verify",
        ]

        other_weak_patterns = [
            (r"['\"]\s*ECB\s*['\"]", "ecb_mode"),
            (r"['\"]DES['\"]", "des_cipher"),
            (r"['\"]3?DES['\"]", "des_cipher"),
            (r"(?:createCipher|Cipher)\s*\(\s*['\"](?:des|rc4|rc2|blowfish)", "weak_cipher"),
            (r"RSA.*?(?:1024|512|768)\b", "weak_rsa"),
            (r"key_?(?:size|length|len)\s*[:=]\s*(?:512|768|1024)\b", "weak_key"),
        ]

        # Weak hash near password context
        for pat, _tag in weak_hash_patterns:
            for m in re.finditer(pat, content, re.IGNORECASE):
                fn_start, fn_end, fn_text = self._extract_function_body(
                    content, m.start(), lines
                )
                if fn_text is None:
                    continue

                near_password = any(
                    re.search(pp, fn_text, re.IGNORECASE)
                    for pp in password_context_patterns
                )
                if near_password:
                    snippets.append(
                        self._snippet(file_path, lines, fn_start, fn_end, lang)
                    )

        # Math.random for tokens/keys
        for pat, _tag in insecure_random_patterns:
            for m in re.finditer(pat, content):
                fn_start, fn_end, fn_text = self._extract_function_body(
                    content, m.start(), lines
                )
                if fn_text is None:
                    continue

                near_security = any(
                    re.search(sp, fn_text, re.IGNORECASE)
                    for sp in security_context_patterns
                )
                if near_security:
                    snippets.append(
                        self._snippet(file_path, lines, fn_start, fn_end, lang)
                    )

        # Other weak crypto patterns (always flag)
        for pat, _tag in other_weak_patterns:
            for m in re.finditer(pat, content, re.IGNORECASE):
                fn_start, fn_end, fn_text = self._extract_function_body(
                    content, m.start(), lines
                )
                if fn_text is None:
                    continue
                snippets.append(
                    self._snippet(file_path, lines, fn_start, fn_end, lang)
                )

        return self._dedupe_snippets(snippets)

    # ── 10. Data Exposure ────────────────────────────────────────────────────

    def _extract_data_exposure(
        self,
        file_path: Path,
        content: str,
        lines: list[str],
        lang: str,
        framework: str,
    ) -> list[CodeSnippet]:
        snippets: list[CodeSnippet] = []

        response_patterns = [
            r"NextResponse\.json\s*\(",
            r"Response\.json\s*\(",
            r"res\.json\s*\(",
            r"res\.send\s*\(",
            r"jsonify\s*\(",
            r"JsonResponse\s*\(",
            r"c\.JSON\s*\(",
            r"ResponseEntity",
        ]

        sensitive_field_patterns = [
            r"\bpassword\b",
            r"\bpasswordHash\b",
            r"\bpassword_hash\b",
            r"\bhashed_password\b",
            r"\bsecret\b",
            r"\bsecretKey\b",
            r"\bsecret_key\b",
            r"\btoken\b(?!.*csrf)",
            r"\bapiKey\b",
            r"\bapi_key\b",
            r"\bssn\b",
            r"\bcreditCard\b",
            r"\bcredit_card\b",
            r"\bcvv\b",
            r"\bprivateKey\b",
            r"\bprivate_key\b",
            r"\baccess_token\b",
            r"\brefresh_token\b",
        ]

        # Stack trace exposure
        error_exposure_patterns = [
            r"catch\s*\(\s*\w+\s*\)\s*\{[^}]*(?:res\.(?:json|send)|NextResponse\.json)\s*\([^)]*(?:\.message|\.stack|error\b|err\b)",
            r"\.stack\b",
            r"traceback\.format_exc\s*\(",
            r"e\.printStackTrace\s*\(",
        ]

        for rp in response_patterns:
            for m in re.finditer(rp, content):
                fn_start, fn_end, fn_text = self._extract_function_body(
                    content, m.start(), lines
                )
                if fn_text is None:
                    continue

                has_sensitive = any(
                    re.search(sf, fn_text, re.IGNORECASE)
                    for sf in sensitive_field_patterns
                )
                if has_sensitive:
                    snippets.append(
                        self._snippet(file_path, lines, fn_start, fn_end, lang)
                    )

        # Error handlers leaking stack traces
        for ep in error_exposure_patterns:
            for m in re.finditer(ep, content, re.DOTALL):
                fn_start, fn_end, fn_text = self._extract_function_body(
                    content, m.start(), lines
                )
                if fn_text is None:
                    continue
                snippets.append(
                    self._snippet(file_path, lines, fn_start, fn_end, lang)
                )

        return self._dedupe_snippets(snippets)

    # ── 11. Command Injection ────────────────────────────────────────────────

    def _extract_command_injection(
        self,
        file_path: Path,
        content: str,
        lines: list[str],
        lang: str,
        framework: str,
    ) -> list[CodeSnippet]:
        snippets: list[CodeSnippet] = []

        shell_exec_patterns = [
            r"(?:child_process\.)?exec\s*\(",
            r"(?:child_process\.)?execSync\s*\(",
            r"(?:child_process\.)?spawn\s*\(",
            r"(?:child_process\.)?spawnSync\s*\(",
            r"subprocess\.run\s*\(",
            r"subprocess\.call\s*\(",
            r"subprocess\.Popen\s*\(",
            r"os\.system\s*\(",
            r"os\.popen\s*\(",
            r"exec\.Command\s*\(",
            r"Runtime\.getRuntime\(\)\.exec\s*\(",
            r"ProcessBuilder\s*\(",
            r"system\s*\(",
            r"`[^`]*\$\{",  # Template literal with interpolation
        ]

        interpolation_patterns = [
            r"\$\{",            # template literal interpolation
            r"\+\s*\w+",        # string concatenation
            r"f['\"].*\{",      # Python f-string
            r"%\s",             # Python % formatting
            r"\.format\s*\(",   # Python .format()
            r"fmt\.Sprintf\s*\(",  # Go Sprintf
            r"String\.format\s*\(",  # Java format
        ]

        safe_patterns = [
            r"(?:shell|shell_exec)\s*[:=]\s*false",
            r"execFile\s*\(",  # execFile is safer than exec
            r"subprocess\.\w+\s*\(\s*\[",  # subprocess with list args (safer)
            r"shlex\.quote\s*\(",
            r"shellescape",
        ]

        for sep in shell_exec_patterns:
            for m in re.finditer(sep, content):
                line_num = content[:m.start()].count("\n")
                # Get a window around the match for context
                window_start = max(0, line_num - 2)
                window_end = min(len(lines), line_num + 5)
                window_text = "\n".join(lines[window_start:window_end])

                has_interpolation = any(
                    re.search(ip, window_text) for ip in interpolation_patterns
                )
                if not has_interpolation:
                    continue

                fn_start, fn_end, fn_text = self._extract_function_body(
                    content, m.start(), lines
                )
                if fn_text is None:
                    continue

                has_safe = any(re.search(sp, fn_text) for sp in safe_patterns)
                if not has_safe:
                    snippets.append(
                        self._snippet(file_path, lines, fn_start, fn_end, lang)
                    )

        return self._dedupe_snippets(snippets)

    # ── 12. XXE ──────────────────────────────────────────────────────────────

    def _extract_xxe(
        self,
        file_path: Path,
        content: str,
        lines: list[str],
        lang: str,
        framework: str,
    ) -> list[CodeSnippet]:
        snippets: list[CodeSnippet] = []

        xml_parser_patterns = [
            r"DOMParser\s*\(",
            r"new\s+DOMParser",
            r"xml\.etree\.ElementTree",
            r"lxml\.etree",
            r"xml\.sax",
            r"xml\.dom\.minidom",
            r"xml2js",
            r"SAXParser",
            r"SAXParserFactory",
            r"XMLReader",
            r"DocumentBuilderFactory",
            r"parseString\s*\(",
            r"parseXML\s*\(",
            r"libxml",
            r"xmlparse",
            r"expat",
        ]

        safe_patterns = [
            r"resolve_entities\s*=\s*False",
            r"no_network\s*=\s*True",
            r"noent",
            r"NOENT",
            r"disallow_doctype",
            r"FEATURE_SECURE_PROCESSING",
            r"setFeature.*disallow-doctype-decl.*true",
            r"defusedxml",
            r"XMLConstants\.FEATURE_SECURE_PROCESSING",
            r"external-general-entities.*false",
            r"external-parameter-entities.*false",
        ]

        for xp in xml_parser_patterns:
            for m in re.finditer(xp, content):
                fn_start, fn_end, fn_text = self._extract_function_body(
                    content, m.start(), lines
                )
                if fn_text is None:
                    # Fall back to a region around the match
                    line_num = content[:m.start()].count("\n")
                    fn_start = max(0, line_num - 5)
                    fn_end = min(len(lines) - 1, line_num + 20)
                    fn_text = "\n".join(lines[fn_start:fn_end + 1])

                has_safe = any(
                    re.search(sp, fn_text, re.IGNORECASE) for sp in safe_patterns
                )
                if not has_safe:
                    snippets.append(
                        self._snippet(file_path, lines, fn_start, fn_end, lang)
                    )

        return self._dedupe_snippets(snippets)

    # ── 13. GraphQL ──────────────────────────────────────────────────────────

    def _extract_graphql(
        self,
        file_path: Path,
        content: str,
        lines: list[str],
        lang: str,
        framework: str,
    ) -> list[CodeSnippet]:
        snippets: list[CodeSnippet] = []

        graphql_patterns = [
            r"(?:buildSchema|makeExecutableSchema|typeDefs|gql`)",
            r"ApolloServer\s*\(",
            r"GraphQLSchema\s*\(",
            r"graphene\.",
            r"strawberry\.",
            r"ariadne\.",
            r"type\s+Query\s*\{",
            r"type\s+Mutation\s*\{",
            r"GraphQLObjectType\s*\(",
            r"new\s+GraphQLServer",
        ]

        missing_security_patterns = {
            "introspection": [
                r"introspection\s*:\s*false",
                r"introspection\s*=\s*False",
                r"disable_introspection",
                r"NoIntrospection",
            ],
            "depth_limit": [
                r"depthLimit",
                r"depth_limit",
                r"maxDepth",
                r"max_depth",
                r"queryDepth",
            ],
            "cost_analysis": [
                r"costAnalysis",
                r"cost_analysis",
                r"queryCost",
                r"complexity",
                r"queryComplexity",
                r"max_complexity",
            ],
        }

        for gp in graphql_patterns:
            for m in re.finditer(gp, content):
                fn_start, fn_end, fn_text = self._extract_function_body(
                    content, m.start(), lines
                )
                if fn_text is None:
                    # Use broader context for config files
                    line_num = content[:m.start()].count("\n")
                    fn_start = max(0, line_num - 10)
                    fn_end = min(len(lines) - 1, line_num + 40)
                    fn_text = "\n".join(lines[fn_start:fn_end + 1])

                missing: list[str] = []
                for check_name, check_patterns in missing_security_patterns.items():
                    if not any(
                        re.search(cp, fn_text, re.IGNORECASE) for cp in check_patterns
                    ):
                        missing.append(check_name)

                # Flag if missing at least one security control
                if missing:
                    snippets.append(
                        self._snippet(file_path, lines, fn_start, fn_end, lang)
                    )

        return self._dedupe_snippets(snippets)

    # ── 14. Prototype Pollution ──────────────────────────────────────────────

    def _extract_prototype_pollution(
        self,
        file_path: Path,
        content: str,
        lines: list[str],
        lang: str,
        framework: str,
    ) -> list[CodeSnippet]:
        snippets: list[CodeSnippet] = []

        merge_patterns = [
            r"Object\.assign\s*\(\s*\{\s*\}\s*,\s*(?:req\.body|body|data|input|params)",
            r"Object\.assign\s*\(\s*\w+\s*,\s*(?:req\.body|body|data|input|params)",
            r"_\.merge\s*\(",
            r"_\.defaultsDeep\s*\(",
            r"_\.extend\s*\(",
            r"deepmerge\s*\(",
            r"deep[_-]?extend\s*\(",
            r"merge\s*\(\s*\w+\s*,\s*(?:req\.body|body|data|input)",
            r"\.\.\.\s*(?:req\.body|body|JSON\.parse)",
            # Dynamic property access with user input
            r"\w+\[\s*(?:key|prop|field|name|k)\s*\]\s*=",
        ]

        safe_patterns = [
            r"__proto__",  # explicitly checking __proto__
            r"prototype",  # checking prototype
            r"constructor",  # checking constructor
            r"hasOwnProperty",
            r"Object\.create\s*\(\s*null\s*\)",
            r"Object\.freeze",
            r"sanitize",
        ]

        for mp in merge_patterns:
            for m in re.finditer(mp, content):
                fn_start, fn_end, fn_text = self._extract_function_body(
                    content, m.start(), lines
                )
                if fn_text is None:
                    continue

                # Only flag if user input flows into merge AND no proto checks
                has_user_input = bool(
                    re.search(
                        r"(?:req\.body|request\.body|body|input|params|data)\b",
                        fn_text,
                    )
                )
                has_safe = any(
                    re.search(sp, fn_text, re.IGNORECASE) for sp in safe_patterns
                )

                if has_user_input and not has_safe:
                    snippets.append(
                        self._snippet(file_path, lines, fn_start, fn_end, lang)
                    )

        return self._dedupe_snippets(snippets)

    # ── 15. Insecure Defaults ────────────────────────────────────────────────

    def _extract_insecure_defaults(
        self,
        file_path: Path,
        content: str,
        lines: list[str],
        lang: str,
        framework: str,
    ) -> list[CodeSnippet]:
        snippets: list[CodeSnippet] = []

        insecure_patterns = [
            # Cookie settings
            (r"secure\s*:\s*false", "insecure_cookie"),
            (r"httpOnly\s*:\s*false", "no_httponly"),
            (r"sameSite\s*:\s*['\"]none['\"]", "samesite_none"),
            (r"http_only\s*=\s*False", "no_httponly"),
            (r"secure\s*=\s*False", "insecure_cookie"),
            # CORS
            (r"origin\s*:\s*['\"\*]?\*['\"]?", "cors_wildcard"),
            (r"Access-Control-Allow-Origin['\"]?\s*[:=]\s*['\"]?\*", "cors_wildcard"),
            (r"cors\s*\(\s*\{[^}]*credentials\s*:\s*true[^}]*origin\s*:\s*(?:true|['\"]?\*)", "cors_credentials_wildcard"),
            (r"allowedOrigins.*\*", "cors_wildcard"),
            # Debug mode
            (r"debug\s*[:=]\s*(?:true|True|1)\b", "debug_enabled"),
            (r"DEBUG\s*=\s*(?:True|1|['\"]1['\"])", "debug_enabled"),
            # Helmet / security headers disabled
            (r"helmet\s*\(\s*\{[^}]*(?:frameguard|xssFilter|noSniff|hsts)\s*:\s*false", "helmet_disabled"),
            (r"contentSecurityPolicy\s*:\s*false", "csp_disabled"),
            # SSL verification
            (r"rejectUnauthorized\s*:\s*false", "ssl_verify_off"),
            (r"verify\s*=\s*False", "ssl_verify_off"),
            (r"NODE_TLS_REJECT_UNAUTHORIZED.*0", "ssl_verify_off"),
            (r"InsecureSkipVerify\s*:\s*true", "ssl_verify_off"),
        ]

        for pat, _tag in insecure_patterns:
            for m in re.finditer(pat, content, re.IGNORECASE):
                line_num = content[:m.start()].count("\n")

                # For debug flags, skip if in test/dev-only context
                if _tag == "debug_enabled":
                    surrounding = "\n".join(
                        lines[max(0, line_num - 3):min(len(lines), line_num + 3)]
                    )
                    if re.search(
                        r"(?:test|spec|dev|development|__tests__|\.test\.|\.spec\.)",
                        surrounding,
                        re.IGNORECASE,
                    ):
                        continue

                fn_start, fn_end, fn_text = self._extract_function_body(
                    content, m.start(), lines
                )
                if fn_text is None:
                    # Use region around match for config files
                    fn_start = max(0, line_num - 5)
                    fn_end = min(len(lines) - 1, line_num + 15)

                snippets.append(
                    self._snippet(file_path, lines, fn_start, fn_end, lang)
                )

        return self._dedupe_snippets(snippets)

    # ── 16. Timing Attacks ───────────────────────────────────────────────────

    def _extract_timing_attacks(
        self,
        file_path: Path,
        content: str,
        lines: list[str],
        lang: str,
        framework: str,
    ) -> list[CodeSnippet]:
        snippets: list[CodeSnippet] = []

        # Patterns: comparison of secrets/tokens using === or ==
        secret_compare_patterns = [
            r"(?:token|apiKey|api_key|secret|password|hash|digest|signature|hmac|key|otp|code)\s*===?\s*(?:req\.|request\.|params\.|query\.|body\.|input\.|headers?\.)",
            r"(?:req\.|request\.|params\.|query\.|body\.|input\.|headers?\.)\w*\s*===?\s*(?:token|apiKey|api_key|secret|password|hash|digest|signature|hmac|key|otp|code)\b",
            r"if\s*\(\s*\w*(?:token|secret|key|hash|code|otp|api_key|apiKey|signature)\w*\s*===?\s*\w+",
            r"if\s*\(\s*\w+\s*===?\s*\w*(?:token|secret|key|hash|code|otp|api_key|apiKey|signature)\w*",
        ]

        safe_patterns = [
            r"timingSafeEqual",
            r"timing_safe_equal",
            r"hmac\.compare_digest",
            r"constant_time_compare",
            r"secure_compare",
            r"crypto\.subtle\.timingSafeEqual",
            r"ConstantTimeCompare",
            r"MessageDigest\.isEqual",
        ]

        for scp in secret_compare_patterns:
            for m in re.finditer(scp, content, re.IGNORECASE):
                fn_start, fn_end, fn_text = self._extract_function_body(
                    content, m.start(), lines
                )
                if fn_text is None:
                    continue

                has_safe = any(
                    re.search(sp, fn_text, re.IGNORECASE) for sp in safe_patterns
                )
                if not has_safe:
                    snippets.append(
                        self._snippet(file_path, lines, fn_start, fn_end, lang)
                    )

        return self._dedupe_snippets(snippets)

    # ── 17. Missing Rate Limit ───────────────────────────────────────────────

    def _extract_missing_rate_limit(
        self,
        file_path: Path,
        content: str,
        lines: list[str],
        lang: str,
        framework: str,
    ) -> list[CodeSnippet]:
        snippets: list[CodeSnippet] = []

        # Check if file is in a public-facing path
        path_str = str(file_path)
        public_path_patterns = [
            r"share/",
            r"webhook",
            r"auth/",
            r"public/",
            r"api/c/",
            r"api/register",
            r"api/login",
            r"api/signup",
            r"api/forgot",
            r"api/reset",
            r"callback",
        ]

        is_public_path = any(
            re.search(pp, path_str, re.IGNORECASE) for pp in public_path_patterns
        )
        if not is_public_path:
            return []

        rate_limit_patterns = [
            r"rateLimit",
            r"rate_limit",
            r"rateLimiter",
            r"checkRateLimit",
            r"throttle",
            r"RateLimiter",
            r"slowDown",
            r"express-rate-limit",
            r"Throttle",
            r"@throttle",
            r"limiter\.",
            r"RATE_LIMIT",
        ]

        handler_re = re.compile(
            r"export\s+(?:async\s+)?function\s+(?:GET|POST|PUT|DELETE|PATCH)\b|"
            r"(?:router|app)\.\s*(?:get|post|put|delete|patch)\s*\(|"
            r"@(?:app|router)\.(?:get|post|put|delete|patch)\(|"
            r"@app\.route\(|"
            r"def\s+(?:get|post|put|delete|patch)\s*\(",
            re.MULTILINE,
        )

        for m in handler_re.finditer(content):
            fn_start, fn_end, fn_text = self._extract_function_body(
                content, m.start(), lines
            )
            if fn_text is None:
                continue

            has_rate_limit = any(
                re.search(rlp, fn_text, re.IGNORECASE) for rlp in rate_limit_patterns
            )

            # Also check file-level rate limiting (middleware at top of file)
            file_top = "\n".join(lines[:20])
            has_file_rate_limit = any(
                re.search(rlp, file_top, re.IGNORECASE) for rlp in rate_limit_patterns
            )

            if not has_rate_limit and not has_file_rate_limit:
                snippets.append(
                    self._snippet(file_path, lines, fn_start, fn_end, lang)
                )

        return self._dedupe_snippets(snippets)

    # ── 18. AI Prompt Injection ──────────────────────────────────────────────

    def _extract_ai_prompt_injection(
        self,
        file_path: Path,
        content: str,
        lines: list[str],
        lang: str,
        framework: str,
    ) -> list[CodeSnippet]:
        snippets: list[CodeSnippet] = []

        llm_call_patterns = [
            r"openai\.chat\.completions\.create\s*\(",
            r"openai\.completions\.create\s*\(",
            r"ChatCompletion\.create\s*\(",
            r"anthropic\.messages\.create\s*\(",
            r"anthropic\.completions\.create\s*\(",
            r"completion\s*\(",
            r"generate\s*\(",
            r"client\.chat\s*\(",
            r"llm\.invoke\s*\(",
            r"chain\.invoke\s*\(",
            r"model\.generate\s*\(",
            r"ChatOpenAI\s*\(",
            r"ChatAnthropic\s*\(",
            r"Anthropic\s*\(",
            r"OpenAI\s*\(",
            r"groq\.chat\.completions",
            r"together\.chat\.completions",
            r"cohere\.chat\s*\(",
        ]

        interpolation_patterns = [
            r"`[^`]*\$\{[^}]*(?:user|input|message|query|prompt|body|request|content|text|question)[^}]*\}[^`]*`",
            r'f["\'][^"\']*\{[^}]*(?:user|input|message|query|prompt|body|request|content|text|question)[^}]*\}',
            r"\+\s*(?:user|input|message|query|prompt|body|request|content|text|question)\w*",
            r"\.format\s*\([^)]*(?:user|input|message|query|prompt|body|request|content|text|question)",
            r"%\s*(?:\(|{).*(?:user|input|message|query|prompt|body|request|content|text|question)",
        ]

        safe_patterns = [
            r"sanitize",
            r"escape",
            r"clean",
            r"strip",
            r"filter",
            r"validate_prompt",
            r"prompt_injection",
            r"guard",
        ]

        for lcp in llm_call_patterns:
            for m in re.finditer(lcp, content, re.IGNORECASE):
                fn_start, fn_end, fn_text = self._extract_function_body(
                    content, m.start(), lines
                )
                if fn_text is None:
                    continue

                has_interpolation = any(
                    re.search(ip, fn_text, re.IGNORECASE)
                    for ip in interpolation_patterns
                )
                has_safe = any(
                    re.search(sp, fn_text, re.IGNORECASE) for sp in safe_patterns
                )

                if has_interpolation and not has_safe:
                    snippets.append(
                        self._snippet(file_path, lines, fn_start, fn_end, lang)
                    )

        return self._dedupe_snippets(snippets)

    # ── Helper methods ───────────────────────────────────────────────────────

    def _extract_function_body(
        self, content: str, match_pos: int, lines: list[str]
    ) -> tuple[int, int, str | None]:
        """From a regex match position, expand to capture the full enclosing function body.

        For brace-based languages (JS/TS/Java/Go/Rust/C#), count braces.
        For Python, use indentation.
        Returns (start_line, end_line, function_text) or (-1, -1, None) if not found.
        """
        match_line = content[:match_pos].count("\n")

        # Walk backward to find the function start
        func_start_patterns = [
            # JS/TS
            r"(?:export\s+)?(?:async\s+)?function\s+\w+",
            r"(?:const|let|var)\s+\w+\s*=\s*(?:async\s+)?\(",
            r"(?:const|let|var)\s+\w+\s*=\s*(?:async\s+)?(?:\([^)]*\)|[a-zA-Z_]\w*)\s*=>",
            # Python
            r"(?:async\s+)?def\s+\w+\s*\(",
            # Go
            r"func\s+(?:\([^)]*\)\s*)?\w+\s*\(",
            # Java
            r"(?:public|private|protected)\s+(?:static\s+)?(?:async\s+)?\w+\s+\w+\s*\(",
            # Class methods
            r"\w+\s*\([^)]*\)\s*(?::\s*\w+)?\s*\{",
            # Ruby
            r"def\s+\w+",
        ]

        fn_start_line = -1
        for scan_line in range(match_line, max(match_line - 50, -1), -1):
            if scan_line < 0:
                break
            line_text = lines[scan_line]
            for fsp in func_start_patterns:
                if re.search(fsp, line_text):
                    fn_start_line = scan_line
                    break
            if fn_start_line >= 0:
                break

        if fn_start_line < 0:
            # Could not find a function start; use a reasonable window
            fn_start_line = max(0, match_line - 5)

        # Determine language style to find function end
        start_text = lines[fn_start_line] if fn_start_line < len(lines) else ""

        is_python = bool(re.search(r"(?:async\s+)?def\s+\w+\s*\(", start_text))
        is_ruby = bool(re.search(r"^\s*def\s+\w+", start_text))

        if is_python:
            return self._extract_python_block(lines, fn_start_line)
        elif is_ruby:
            return self._extract_ruby_block(lines, fn_start_line)
        else:
            return self._extract_brace_block(lines, fn_start_line)

    def _extract_brace_block(
        self, lines: list[str], start_line: int
    ) -> tuple[int, int, str | None]:
        """Extract a brace-delimited block ({...}) starting from start_line."""
        brace_depth = 0
        found_open = False
        end_line = start_line

        for i in range(start_line, min(len(lines), start_line + self.max_snippet_lines + 50)):
            line = lines[i]
            # Skip strings in a simplistic way (not perfect, but good enough)
            in_string = False
            escaped = False
            for ch in line:
                if escaped:
                    escaped = False
                    continue
                if ch == "\\":
                    escaped = True
                    continue
                if ch in ("'", '"', "`"):
                    in_string = not in_string
                    continue
                if in_string:
                    continue
                if ch == "{":
                    brace_depth += 1
                    found_open = True
                elif ch == "}":
                    brace_depth -= 1

            if found_open and brace_depth <= 0:
                end_line = i
                break
            end_line = i

        if not found_open:
            # No braces found, return a window
            end_line = min(len(lines) - 1, start_line + 30)

        text = "\n".join(lines[start_line:end_line + 1])
        return start_line, end_line, text

    def _extract_python_block(
        self, lines: list[str], start_line: int
    ) -> tuple[int, int, str | None]:
        """Extract a Python function body using indentation."""
        if start_line >= len(lines):
            return -1, -1, None

        # Get the indentation of the def line
        def_line = lines[start_line]
        def_indent = len(def_line) - len(def_line.lstrip())

        end_line = start_line

        # Handle multi-line def with parens
        paren_depth = 0
        i = start_line
        while i < len(lines):
            paren_depth += lines[i].count("(") - lines[i].count(")")
            if paren_depth <= 0:
                break
            i += 1

        body_start = i + 1

        for j in range(body_start, min(len(lines), start_line + self.max_snippet_lines)):
            line = lines[j]
            stripped = line.strip()

            # Skip blank lines and comments
            if not stripped or stripped.startswith("#"):
                end_line = j
                continue

            current_indent = len(line) - len(line.lstrip())
            if current_indent <= def_indent and stripped:
                # We've left the function body (new top-level statement)
                # But check for decorators of the next function
                if stripped.startswith("@") or stripped.startswith("def ") or stripped.startswith("class "):
                    break
                break
            end_line = j

        text = "\n".join(lines[start_line:end_line + 1])
        return start_line, end_line, text

    def _extract_ruby_block(
        self, lines: list[str], start_line: int
    ) -> tuple[int, int, str | None]:
        """Extract a Ruby method body using def...end."""
        depth = 0
        end_line = start_line

        block_openers = re.compile(
            r"\b(?:def|do|class|module|if|unless|while|until|for|begin|case)\b"
        )
        block_closers = re.compile(r"\bend\b")

        for i in range(start_line, min(len(lines), start_line + self.max_snippet_lines)):
            line = lines[i].strip()
            depth += len(block_openers.findall(line))
            depth -= len(block_closers.findall(line))
            end_line = i
            if depth <= 0 and i > start_line:
                break

        text = "\n".join(lines[start_line:end_line + 1])
        return start_line, end_line, text

    def _infer_route_path(self, file_path: Path) -> str:
        """Convert file paths to route paths.

        Examples:
            app/api/users/[id]/route.ts       -> /api/users/:id
            app/api/tables/[tableId]/rows/route.ts -> /api/tables/:tableId/rows
            pages/api/auth/login.ts           -> /api/auth/login
            src/routes/users.py               -> /users
        """
        path_str = str(file_path)

        # Next.js App Router: app/api/.../route.ts
        app_match = re.search(r"app/(.*?)(?:/route\.(?:ts|js)|/page\.(?:ts|tsx|js|jsx))$", path_str)
        if app_match:
            route = "/" + app_match.group(1)
            # Convert [param] to :param
            route = re.sub(r"\[(\w+)\]", r":\1", route)
            # Remove route group wrappers like (app)
            route = re.sub(r"\([^)]+\)/", "", route)
            return route

        # Next.js Pages Router: pages/api/.../file.ts
        pages_match = re.search(r"pages/(.*?)\.(?:ts|tsx|js|jsx)$", path_str)
        if pages_match:
            route = "/" + pages_match.group(1)
            route = re.sub(r"\[(\w+)\]", r":\1", route)
            return route

        # Flask/FastAPI: look in decorators (handled by extract methods)
        # Express: routes/... directory
        routes_match = re.search(r"routes?/(.*?)\.(?:ts|js|py|rb|go|java)$", path_str)
        if routes_match:
            return "/" + routes_match.group(1)

        # Fall back to a cleaned file path
        src_match = re.search(r"(?:src|app)/(.*?)\.(?:ts|tsx|js|jsx|py|rb|go|java)$", path_str)
        if src_match:
            return "/" + src_match.group(1)

        return str(file_path)

    def _detect_http_method(self, content: str, lang: str) -> str:
        """Detect HTTP methods from the source code."""
        methods_found: list[str] = []

        patterns = [
            # Next.js App Router exports
            (r"export\s+(?:async\s+)?function\s+(GET)\b", "GET"),
            (r"export\s+(?:async\s+)?function\s+(POST)\b", "POST"),
            (r"export\s+(?:async\s+)?function\s+(PUT)\b", "PUT"),
            (r"export\s+(?:async\s+)?function\s+(DELETE)\b", "DELETE"),
            (r"export\s+(?:async\s+)?function\s+(PATCH)\b", "PATCH"),
            # Decorators
            (r"@(?:app|router)\.get\b", "GET"),
            (r"@(?:app|router)\.post\b", "POST"),
            (r"@(?:app|router)\.put\b", "PUT"),
            (r"@(?:app|router)\.delete\b", "DELETE"),
            (r"@(?:app|router)\.patch\b", "PATCH"),
            # Express
            (r"(?:router|app)\.get\s*\(", "GET"),
            (r"(?:router|app)\.post\s*\(", "POST"),
            (r"(?:router|app)\.put\s*\(", "PUT"),
            (r"(?:router|app)\.delete\s*\(", "DELETE"),
            (r"(?:router|app)\.patch\s*\(", "PATCH"),
            # Java Spring
            (r"@GetMapping", "GET"),
            (r"@PostMapping", "POST"),
            (r"@PutMapping", "PUT"),
            (r"@DeleteMapping", "DELETE"),
            (r"@PatchMapping", "PATCH"),
            # Python methods
            (r"methods\s*=\s*\[.*?'GET'", "GET"),
            (r"methods\s*=\s*\[.*?'POST'", "POST"),
        ]

        for pattern, method in patterns:
            if re.search(pattern, content, re.IGNORECASE):
                if method not in methods_found:
                    methods_found.append(method)

        return ",".join(methods_found) if methods_found else "unknown"

    def _snippet(
        self,
        file_path: Path,
        content_lines: list[str],
        start: int,
        end: int,
        lang: str,
    ) -> CodeSnippet:
        """Create a CodeSnippet, clamping to max_snippet_lines."""
        # Clamp to valid range
        start = max(0, start)
        end = min(len(content_lines) - 1, end)

        # Enforce max_snippet_lines
        if end - start + 1 > self.max_snippet_lines:
            end = start + self.max_snippet_lines - 1

        text = "\n".join(content_lines[start:end + 1])

        return CodeSnippet(
            file_path=str(file_path),
            start_line=start + 1,  # 1-indexed for display
            end_line=end + 1,
            content=text,
            language=lang,
        )

    def _dedupe_snippets(self, snippets: list[CodeSnippet]) -> list[CodeSnippet]:
        """Remove duplicate or substantially overlapping snippets."""
        if len(snippets) <= 1:
            return snippets

        deduped: list[CodeSnippet] = []
        seen_ranges: list[tuple[str, int, int]] = []

        for s in snippets:
            key = (s.file_path, s.start_line, s.end_line)

            # Check for exact or overlapping ranges
            is_dup = False
            for existing_path, existing_start, existing_end in seen_ranges:
                if existing_path != s.file_path:
                    continue
                # Check overlap: ranges overlap if one starts before the other ends
                overlap_start = max(s.start_line, existing_start)
                overlap_end = min(s.end_line, existing_end)
                if overlap_start <= overlap_end:
                    overlap_size = overlap_end - overlap_start + 1
                    snippet_size = s.end_line - s.start_line + 1
                    existing_size = existing_end - existing_start + 1
                    # If >70% overlap with either, skip
                    if (
                        snippet_size > 0
                        and existing_size > 0
                        and (
                            overlap_size / snippet_size > 0.7
                            or overlap_size / existing_size > 0.7
                        )
                    ):
                        is_dup = True
                        break

            if not is_dup:
                deduped.append(s)
                seen_ranges.append(key)

        return deduped
