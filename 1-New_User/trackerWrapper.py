from OAuth import UK1setup #perform auth
from OAuth.config import init

def main():
    #call config.init to ask for project
    init(UK1setup.bearer, UK1setup.env, debug=[])



main()