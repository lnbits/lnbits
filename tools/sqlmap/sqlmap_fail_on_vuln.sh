#!/bin/bash

files=$( ls ./sqlmap_requests/*.txt)
echo "Files: $files"

for file in $files; do
    echo "################ Running test with $file ################"

    logfile=$(basename "$file" ".log")
    # Run sqlmap and save output
    python sqlmap.py -r $file \
    --skip="usr" \
    --batch --level=2 --risk=2 \
    --ignore-code=400 --ignore-code=401 \
    --dbms=SQLite,PostgreSQL \
    --time-sec 5 2>&1 | tee $logfile

    

    # Check for vulnerability indicators in output
    if grep -q "Parameter:.*is vulnerable" $logfile || grep -q "sqlmap identified the following injection point" $logfile; then
        echo "Vulnerability found for $file!"
        exit 1  # Exit with failure
    else
        echo "No vulnerabilities found for $file."
    fi
    echo "################ Done $file ################"

done
echo "Done"



