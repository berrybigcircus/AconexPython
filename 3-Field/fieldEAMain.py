from OAuth import EAsetup, UK1setup
from OAuth.config import init

# import exporting
# import inspectionRenamer
# import inspectionDuplicator
import inspectionPDF

import IssuesPhotos

#exporting.main(EAsetup.bearer, "https://ea1.aconex.com")  #pass in environment, for urls
#inspectionRenamer.main(EAsetup.bearer, "https://ea1.aconex.com")
#inspectionDuplicator.main(EAsetup.bearer, "https://ea1.aconex.com")


#inspectionPDF.main(EAsetup.bearer, "https://ea1.aconex.com")

init(EAsetup.bearer, EAsetup.env, debug=["HB Test", "1879048648", "TEST"])
IssuesPhotos.main()
