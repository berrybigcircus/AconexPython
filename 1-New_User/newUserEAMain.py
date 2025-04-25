
from OAuth import EAsetup #perform EA auth
import newUser

newUser.main(EAsetup.bearer, "https://ea1.aconex.com")  #pass in environment, for urls
#newUser.updateTracker("HB Test", userData)
