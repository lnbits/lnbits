from fastapi import Request
from fastapi.params import Depends
# from fastapi.templating import Jinja2Templates
from starlette.responses import HTMLResponse

from lnbits.core.models import User
from lnbits.decorators import check_user_exists

from . import jitsi_ext, jitsi_renderer

# templates = Jinja2Templates(directory = 'templates')

@jitsi_ext.get('/', response_class = HTMLResponse)
async def index(request: Request, user: User = Depends(check_user_exists)):
    return jitsi_renderer().TemplateResponse(
            'jitsi/index.html', {'request': request, 'user': user.dict()}
    )
