"""Compare HMAC signature generation."""
import hmac
import hashlib
import base64

# 使用官方SDK的签名逻辑
def sdk_build_hmac_signature(secret, timestamp, method, requestPath, body=None):
    base64_secret = base64.urlsafe_b64decode(secret)
    message = str(timestamp) + str(method) + str(requestPath)
    if body:
        # NOTE: Necessary to replace single quotes with double quotes
        message += str(body).replace("'", '"')
    h = hmac.new(base64_secret, bytes(message, "utf-8"), hashlib.sha256)
    return (base64.urlsafe_b64encode(h.digest())).decode("utf-8")

# 我们的签名逻辑
def our_build_hmac_signature(secret, timestamp, method, requestPath, body=None):
    base64_secret = base64.urlsafe_b64decode(secret)
    message = f"{timestamp}{method}{requestPath}"
    if body:
        message += body
    h = hmac.new(base64_secret, message.encode("utf-8"), hashlib.sha256)
    return base64.urlsafe_b64encode(h.digest()).decode("utf-8")

# Test
secret = "IQUsJZRyONkgmUxSoBvXeisygV4xG4eNqZJhpie05cI="
timestamp = "1234567890"
method = "POST"
path = "/order"
body = '{"test":"data"}'

print("SDK signature:", sdk_build_hmac_signature(secret, timestamp, method, path, body))
print("Our signature:", our_build_hmac_signature(secret, timestamp, method, path, body))

# Same?
sdk_sig = sdk_build_hmac_signature(secret, timestamp, method, path, body)
our_sig = our_build_hmac_signature(secret, timestamp, method, path, body)
print("Signatures match:", sdk_sig == our_sig)
