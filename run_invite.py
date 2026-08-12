from Setup import UK1setup
from Setup.config import init
from a_Directory import Directory

def main():
    init(UK1setup.bearer, UK1setup.env, debug=[])  # Select project
    Directory.main()
    input()


main()