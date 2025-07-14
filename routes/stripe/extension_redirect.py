from fastapi.responses import HTMLResponse
from fastapi import Request
from . import router

@router.get('/redirect', response_class=HTMLResponse)
async def stripe_extension_redirect(request: Request):
    """Return an HTML page that redirects back to the Chrome extension."""
    params = request.query_params
    payment = params.get('payment', '')
    session_id = params.get('session_id', '')
    extension_id = params.get('ext') or params.get('extension_id')
    if not extension_id:
        return HTMLResponse('<html><body>Missing extension id</body></html>', status_code=400)

    redirect_url = f"chrome-extension://{extension_id}/index.html?payment={payment}&session_id={session_id}"
    html_content = f"""<html><head><meta http-equiv='refresh' content='0;url={redirect_url}'/></head>
    <body>If you are not redirected automatically, <a href='{redirect_url}'>click here</a>.</body></html>"""
    return HTMLResponse(content=html_content)
