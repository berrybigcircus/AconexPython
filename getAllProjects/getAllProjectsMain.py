from OAuth import UK1setup, EAsetup
from OAuth.config import init

import getAllProjects

init(UK1setup.bearer, UK1setup.env, debug=None)

getAllProjects.main()
