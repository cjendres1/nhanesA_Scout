library(nhanesA)

# List of all standard NHANES components
components <- c("demographics", "dietary", "examination", "laboratory", "questionnaire")
global_manifest <- data.frame()

message("Pulling complete NHANES variable metadata...")
for (comp in components) {
  tryCatch({
    message(paste("Processing component:", comp))
    # Let nhanesA populate its native 'Component' column
    comp_vars <- nhanesManifest("variables", component = comp, verbose = TRUE)
    global_manifest <- rbind(global_manifest, comp_vars)
  }, error = function(e) {
    message(paste("Error fetching component:", comp, "-", e$message))
  })
}

# Standardize column names to uppercase
colnames(global_manifest) <- toupper(colnames(global_manifest))

# 1. Save the full master variable list
write.csv(global_manifest, "cache_variables_manifest.csv", row.names = FALSE)

# 2. Extract and save the unique tables catalog (preserving the true COMPONENT mapping)
unique_tables <- unique(global_manifest[, c("TABLE", "TABLEDESC", "BEGINYEAR", "ENDYEAR", "COMPONENT")])
write.csv(unique_tables, "cache_demo_manifest.csv", row.names = FALSE)

message("Success! Caches with accurate components generated.")
