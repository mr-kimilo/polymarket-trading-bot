---
applyTo: "**/*.py"
description: "Comprehensive secure coding instructions for Python based on OWASP Top 10 and industry best practices."
---

# Secure Coding and OWASP Guidelines for Python

## Instructions

Your primary directive is to ensure all Python code you generate, review, or refactor is secure by default. You must operate with a security-first mindset. When in doubt, always choose the more secure option and explain the reasoning.

### 1. A01: Broken Access Control & A10: SSRF

- **Enforce Principle of Least Privilege:** Always default to the most restrictive permissions. When generating access control logic, explicitly check the user's rights against the required permissions.
- **Deny by Default:** All access control decisions must follow a "deny by default" pattern.
- **Validate All Incoming URLs for SSRF:** When the server needs to make a request to a URL provided by a user, treat it as untrusted. Use allow-list-based validation.

  ```python
  # GOOD: Validate URL against allow list
  from urllib.parse import urlparse

  ALLOWED_HOSTS = ['api.example.com', 'cdn.example.com']

  def is_safe_url(url: str) -> bool:
      parsed = urlparse(url)
      return parsed.hostname in ALLOWED_HOSTS and parsed.scheme in ['https']
  ```

- **Prevent Path Traversal:** Sanitize file paths to prevent directory traversal attacks.

  ```python
  # GOOD: Use pathlib for safe path handling
  from pathlib import Path

  def safe_read_file(filename: str, base_dir: Path) -> str:
      file_path = (base_dir / filename).resolve()
      if not str(file_path).startswith(str(base_dir.resolve())):
          raise ValueError("Path traversal detected")
      return file_path.read_text()
  ```

### 2. A02: Cryptographic Failures

- **Use Strong, Modern Algorithms:** For password hashing, use bcrypt, Argon2, or scrypt. Never use MD5 or SHA-1 for passwords.

  ```python
  # GOOD: Use bcrypt for password hashing
  import bcrypt

  def hash_password(password: str) -> bytes:
      return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())

  def verify_password(password: str, hashed: bytes) -> bool:
      return bcrypt.checkpw(password.encode('utf-8'), hashed)
  ```

- **Protect Data in Transit:** Always use HTTPS for network requests.

  ```python
  # GOOD: Enforce HTTPS
  import requests

  response = requests.get('https://api.example.com', verify=True)
  ```

- **Protect Data at Rest:** Use cryptography library for encryption.

  ```python
  # GOOD: Encrypt sensitive data
  from cryptography.fernet import Fernet

  def encrypt_data(data: str, key: bytes) -> bytes:
      f = Fernet(key)
      return f.encrypt(data.encode())
  ```

- **Secure Secret Management:** Never hardcode secrets. Use environment variables or secret managers.

  ```python
  # GOOD: Load from environment
  import os
  from typing import Optional

  def get_api_key() -> Optional[str]:
      return os.getenv('API_KEY')

  # BAD: Hardcoded secret
  # api_key = "sk_live_this_is_very_bad_12345"
  ```

### 3. A03: Injection

- **No Raw SQL Queries:** Use parameterized queries with SQLAlchemy or similar ORMs.

  ```python
  # GOOD: Parameterized query with SQLAlchemy
  from sqlalchemy import text

  result = session.execute(
      text("SELECT * FROM users WHERE email = :email"),
      {"email": user_email}
  )

  # BAD: String concatenation (SQL injection vulnerable)
  # query = f"SELECT * FROM users WHERE email = '{user_email}'"
  ```

- **Sanitize Command-Line Input:** Use subprocess with list arguments, never shell=True with user input.

  ```python
  # GOOD: Safe command execution
  import subprocess

  subprocess.run(['ls', '-la', user_directory], check=True)

  # BAD: Shell injection vulnerable
  # subprocess.run(f"ls -la {user_directory}", shell=True)
  ```

- **Prevent Cross-Site Scripting (XSS):** For web frameworks, use template auto-escaping. For FastAPI/Pydantic, data is automatically validated.

  ```python
  # GOOD: Jinja2 auto-escaping (default)
  from jinja2 import Template

  template = Template("<p>{{ user_input }}</p>")  # Auto-escaped

  # If you must render HTML, use bleach
  import bleach

  clean_html = bleach.clean(user_html, tags=['p', 'br'], strip=True)
  ```

- **Avoid Pickle with Untrusted Data:** Never unpickle data from untrusted sources. Use JSON instead.

  ```python
  # GOOD: Use JSON for serialization
  import json

  data = json.loads(untrusted_input)

  # BAD: Pickle is vulnerable to code execution
  # import pickle
  # data = pickle.loads(untrusted_input)  # NEVER DO THIS
  ```

### 4. A05: Security Misconfiguration & A06: Vulnerable Components

- **Secure by Default Configuration:** Disable debug mode in production.

  ```python
  # GOOD: Environment-based configuration
  import os

  DEBUG = os.getenv('DEBUG', 'False').lower() == 'true'
  ```

- **Set Security Headers:** For web applications (FastAPI example):

  ```python
  from fastapi import FastAPI
  from fastapi.middleware.cors import CORSMiddleware
  from starlette.middleware.trustedhost import TrustedHostMiddleware

  app = FastAPI()

  # Security headers
  @app.middleware("http")
  async def add_security_headers(request, call_next):
      response = await call_next(request)
      response.headers["X-Content-Type-Options"] = "nosniff"
      response.headers["X-Frame-Options"] = "DENY"
      response.headers["Strict-Transport-Security"] = "max-age=31536000"
      return response
  ```

- **Use Up-to-Date Dependencies:** Regularly run vulnerability scanners.
  ```bash
  pip-audit  # Check for known vulnerabilities
  safety check  # Alternative scanner
  ```

### 5. A07: Identification & Authentication Failures

- **Secure Session Management:** Use secure session cookies with proper attributes.

  ```python
  # GOOD: Secure session configuration (FastAPI example)
  from fastapi import FastAPI, Response

  response.set_cookie(
      key="session_id",
      value=session_id,
      httponly=True,
      secure=True,  # HTTPS only
      samesite='strict'
  )
  ```

- **Protect Against Brute Force:** Implement rate limiting.

  ```python
  # GOOD: Rate limiting with slowapi (FastAPI)
  from slowapi import Limiter
  from slowapi.util import get_remote_address

  limiter = Limiter(key_func=get_remote_address)

  @app.post("/login")
  @limiter.limit("5/minute")
  async def login(request: Request):
      pass
  ```

### 6. A08: Software and Data Integrity Failures

- **Prevent Insecure Deserialization:** Use JSON instead of pickle. Validate data types with Pydantic.

  ```python
  # GOOD: Use Pydantic for validation
  from pydantic import BaseModel, validator

  class UserInput(BaseModel):
      email: str
      age: int

      @validator('email')
      def validate_email(cls, v):
          if '@' not in v:
              raise ValueError('Invalid email')
          return v
  ```

### 7. Python-Specific Security Concerns

#### Eval and Exec

```python
# BAD: Never use eval with user input
# result = eval(user_input)  # Code execution vulnerability

# GOOD: Use ast.literal_eval for safe evaluation
from ast import literal_eval

result = literal_eval(user_input)  # Only evaluates literals
```

#### Import Security

```python
# BAD: Dynamic imports with user input
# module = __import__(user_module_name)

# GOOD: Whitelist allowed modules
ALLOWED_MODULES = {'math', 'datetime', 'json'}

def safe_import(module_name: str):
    if module_name not in ALLOWED_MODULES:
        raise ValueError("Module not allowed")
    return __import__(module_name)
```

#### Regular Expression DoS (ReDoS)

```python
# BAD: Vulnerable to ReDoS
# pattern = re.compile(r'(a+)+b')

# GOOD: Use simple patterns or timeout
import re

pattern = re.compile(r'a+b')  # Linear time complexity
```

## Security Checklist for Python

- [ ] Input validation on all public methods (use Pydantic)
- [ ] SQL injection prevention (parameterized queries, SQLAlchemy ORM)
- [ ] XSS protection (template escaping, bleach for HTML)
- [ ] Authorization checks on sensitive operations
- [ ] Secure configuration (env vars, no hardcoded secrets)
- [ ] Error handling without information disclosure
- [ ] Dependency scanning (`pip-audit`, `safety check`)
- [ ] No use of `eval`, `exec`, `pickle` with untrusted input
- [ ] HTTPS enforced for external requests
- [ ] Path traversal prevention (pathlib, input validation)
- [ ] Rate limiting on authentication endpoints
- [ ] OWASP Top 10 considerations addressed

## General Guidelines

- **Be Explicit About Security:** When suggesting code that mitigates a security risk, state what you're protecting against.
- **Educate During Code Reviews:** Explain the risk associated with insecure patterns.
- **Use Type Hints:** They help catch errors early and improve security.
- **Validate Early:** Validate all inputs at the boundary using Pydantic or similar.
- **Log Security Events:** Log authentication failures, authorization denials, and suspicious activity.
