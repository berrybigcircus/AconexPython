from OAuth import EAsetup #perform EA auth

import exporting
import inspectionRenamer
import inspectionDuplicator
import inspectionPDF

#exporting.main(EAsetup.bearer, "https://ea1.aconex.com")  #pass in environment, for urls
#inspectionRenamer.main(EAsetup.bearer, "https://ea1.aconex.com")
#inspectionDuplicator.main(EAsetup.bearer, "https://ea1.aconex.com")


inspectionPDF.main(EAsetup.bearer, "https://ea1.aconex.com")
