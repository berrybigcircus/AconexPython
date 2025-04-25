
from OAuth import UK1setup #perform auth
import newUser

newUser.main(UK1setup.bearer, "https://uk1.aconex.co.uk")  #pass in environment, for urls
#newUser.updateTracker("HB Test", userData)