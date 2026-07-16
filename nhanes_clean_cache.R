library(nhanesA)

message("Downloading the master NHANES variable manifest...")
# Running without a component argument pulls ALL components (Demographics, Lab, Dietary, Exam, Questionnaire) at once
global_manifest <- nhanesManifest("variables", verbose = TRUE)

# Standardize column names to uppercase immediately to prevent any casing discrepancies
colnames(global_manifest) <- toupper(colnames(global_manifest))

# 1. Save the clean, master variables manifest
write.csv(global_manifest, "cache_variables_manifest.csv", row.names = FALSE)

# 2. Extract and save the unique tables catalog (using the true COMPONENT column)
unique_tables <- unique(global_manifest[, c("TABLE", "TABLEDESC", "BEGINYEAR", "ENDYEAR", "COMPONENT")])
write.csv(unique_tables, "cache_demo_manifest.csv", row.names = FALSE)

message("Success! Verified cache files written with true components.")
