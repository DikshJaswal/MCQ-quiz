"""Small security middleware."""

CSP_POLICY = "; ".join(
    [
        "default-src 'self'",
        "script-src 'self'",
        "style-src 'self'",
        "img-src 'self'",
        "font-src 'self'",
        "connect-src 'self'",
        "object-src 'none'",
        "base-uri 'self'",
        "form-action 'self'",
        "frame-ancestors 'none'",
    ]
)

class ContentSecurityPolicyMiddleware:
    """Adds a Content-Security-Policy header to every response except Django admin
    (the admin ships a few inline snippets that a strict policy would break)."""
    def __init__(self, get_response):
        self.get_response = get_response
    def __call__(self, request):
        response = self.get_response(request)
        if not request.path.startswith("/admin/") and "Content-Security-Policy" not in response:
            response["Content-Security-Policy"] = CSP_POLICY
        return response