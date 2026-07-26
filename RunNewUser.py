from Setup import UK1setup
from Setup.config import init
from a_NewUser import newUser

def main():
    init(UK1setup.bearer, UK1setup.env, debug=[])  # Select project
    newUser.main()
    input()


main()