#!/bin/bash
OUTDIR="C:/Users/876762330/Desktop/projects/osteo-vision/output/literature/papers"
mkdir -p "$OUTDIR"
EMAIL="researcher@example.com"
LOG="/tmp/download_log.txt"
> "$LOG"

download_paper() {
    local id="$1"
    local doi="$2"
    local title="$3"

    if [ -z "$doi" ]; then
        echo "$id|NO_DOI|skipped" >> "$LOG"
        return
    fi

    local clean_doi=$(echo "$doi" | sed 's|https://doi.org/||')
    local safe_title=$(echo "$title" | sed 's/[^a-zA-Z0-9._-]/_/g' | head -c 60)
    local outfile="${OUTDIR}/${id}_${safe_title}.pdf"

    if [ -f "$outfile" ]; then
        local fsize=$(wc -c < "$outfile")
        if [ "$fsize" -gt 10000 ]; then
            echo "$id|EXISTS|$outfile" >> "$LOG"
            return
        fi
    fi

    local downloaded=0

    # Strategy 1: EuropePMC
    if [ $downloaded -eq 0 ]; then
        local epmc_json=$(curl -sL --max-time 15 "https://www.ebi.ac.uk/europepmc/webservices/rest/search?query=DOI:${clean_doi}&format=json&resultType=core" 2>/dev/null)
        local pmcid=$(echo "$epmc_json" | grep -o '"pmcid":"PMC[0-9]*"' | head -1 | sed 's/"pmcid":"//;s/"//')
        if [ -n "$pmcid" ]; then
            curl -sL --max-time 60 -o "$outfile" "https://europepmc.org/api/getPdf?pmcid=${pmcid}" 2>/dev/null
            if [ -f "$outfile" ]; then
                local fsize=$(wc -c < "$outfile")
                if [ "$fsize" -gt 10000 ]; then
                    echo "$id|europepmc|$outfile" >> "$LOG"
                    downloaded=1
                else
                    rm -f "$outfile"
                fi
            fi
        fi
    fi

    # Strategy 2: Semantic Scholar
    if [ $downloaded -eq 0 ]; then
        local ss_json=$(curl -sL --max-time 15 "https://api.semanticscholar.org/graph/v1/paper/DOI:${clean_doi}?fields=openAccessPdf" 2>/dev/null)
        local ss_pdf=$(echo "$ss_json" | grep -o '"url":"[^"]*"' | head -1 | sed 's/"url":"//;s/"//')
        if [ -n "$ss_pdf" ] && [ "$ss_pdf" != "null" ] && [ "$ss_pdf" != "" ]; then
            curl -sL --max-time 60 -o "$outfile" "$ss_pdf" 2>/dev/null
            if [ -f "$outfile" ]; then
                local fsize=$(wc -c < "$outfile")
                local header=$(head -c 4 "$outfile" 2>/dev/null)
                if [ "$fsize" -gt 10000 ] && echo "$header" | grep -q '%PDF'; then
                    echo "$id|semanticscholar|$outfile" >> "$LOG"
                    downloaded=1
                else
                    rm -f "$outfile"
                fi
            fi
        fi
    fi

    # Strategy 3: Direct publisher PDF links
    if [ $downloaded -eq 0 ]; then
        local direct_urls=()

        # MDPI
        if echo "$clean_doi" | grep -q "^10.3390/"; then
            local mdpi_path=$(echo "$clean_doi" | sed 's|10.3390/||')
            direct_urls+=("https://www.mdpi.com/${mdpi_path}/pdf")
        fi

        # Frontiers
        if echo "$clean_doi" | grep -q "^10.3389/"; then
            direct_urls+=("https://www.frontiersin.org/articles/${clean_doi}/pdf")
        fi

        # PLOS
        if echo "$clean_doi" | grep -q "^10.1371/"; then
            local plos_id=$(echo "$clean_doi" | sed 's|10.1371/journal.pone.||;s|10.1371/journal.pmed.||')
            direct_urls+=("https://journals.plos.org/plosone/article/file?id=${clean_doi}&type=printable")
        fi

        # Springer/BMC
        if echo "$clean_doi" | grep -qE "^10.1186/|^10.1007/"; then
            direct_urls+=("https://link.springer.com/content/pdf/${clean_doi}.pdf")
        fi

        # Nature
        if echo "$clean_doi" | grep -q "^10.1038/"; then
            local nat_path=$(echo "$clean_doi" | sed 's|10.1038/||')
            direct_urls+=("https://www.nature.com/articles/${nat_path}.pdf")
        fi

        # SAGE
        if echo "$clean_doi" | grep -q "^10.1177/"; then
            direct_urls+=("https://journals.sagepub.com/doi/pdf/${clean_doi}")
        fi

        # Wiley
        if echo "$clean_doi" | grep -qE "^10.1002/|^10.1111/"; then
            direct_urls+=("https://onlinelibrary.wiley.com/doi/pdfdirect/${clean_doi}")
        fi

        # Elsevier/ScienceDirect - use DOI redirect
        if echo "$clean_doi" | grep -q "^10.1016/"; then
            direct_urls+=("https://doi.org/${clean_doi}")
        fi

        # Thieme
        if echo "$clean_doi" | grep -qE "^10.1055/"; then
            direct_urls+=("https://www.thieme-connect.de/products/ejournals/pdf/${clean_doi}.pdf")
        fi

        # De Gruyter
        if echo "$clean_doi" | grep -q "^10.1515/"; then
            direct_urls+=("https://www.degruyter.com/document/doi/${clean_doi}/pdf")
        fi

        for durl in "${direct_urls[@]}"; do
            if [ $downloaded -eq 1 ]; then break; fi
            curl -sL --max-time 60 -o "$outfile" "$durl" 2>/dev/null
            if [ -f "$outfile" ]; then
                local fsize=$(wc -c < "$outfile")
                if [ "$fsize" -gt 10000 ]; then
                    echo "$id|direct|$outfile" >> "$LOG"
                    downloaded=1
                else
                    rm -f "$outfile"
                fi
            fi
        done
    fi

    if [ $downloaded -eq 0 ]; then
        echo "$id|FAILED|$doi" >> "$LOG"
    fi
}

echo "Starting batch download of pending papers..."
download_paper "P056" "https://doi.org/10.1016/j.idc.2025.02.015" "Jaw Osteomyelitis"
download_paper "P057" "https://doi.org/10.2106/JBJS.24.01436" "Intraoperative Bone Perfusion Assessment Fluorescence"
download_paper "P058" "https://doi.org/10.1007/s00223-025-01354-0" "Bisphosphonates Chronic Nonbacterial Osteomyelitis Mandible"
download_paper "P059" "https://doi.org/10.3390/children12050645" "AI Medical Imaging Paediatric Hip Disorders"
download_paper "P060" "https://doi.org/10.12200/j.issn.1003-0034.20240445" "Imaging Techniques Chronic Osteomyelitis"
download_paper "P061" "https://doi.org/10.1016/j.suronc.2024.102091" "NIR Fluorescence ICG Bone Soft Tissue Tumours"
download_paper "P062" "https://doi.org/10.3389/fimmu.2024.1368099" "Bone Marrow Endothelial Progenitor Septic Infection"
download_paper "P063" "https://doi.org/10.17116/stomat202410306173" "Primary Chronic Osteomyelitis Mandible Children"
download_paper "P064" "https://doi.org/10.1002/ctm2.70082" "ER Stress Lymphatic Dysfunction Bisphosphonate Osteonecrosis"
download_paper "P065" "https://doi.org/10.1016/j.jbo.2024.100525" "ChatGPT Bone Tumors Imaging Diagnosis"
download_paper "P066" "https://doi.org/10.1093/dmfr/twae028" "Multiclass Jaw Lesions CBCT Deep Learning"
download_paper "P067" "" "Radiologic Osteonecrosis Osteomyelitis CBCT"
download_paper "P068" "https://doi.org/10.1016/j.amjoto.2024.104343" "ICG Fluorescence Landmark Arteries Sinus Skull Base"
download_paper "P069" "https://doi.org/10.12659/MSM.943168" "Vertebral Osteomyelitis Imaging Review"
download_paper "P070" "https://doi.org/10.1007/s10278-024-01067-0" "DL Diabetic Foot Osteomyelitis Charcot"
download_paper "P071" "https://doi.org/10.1371/journal.pone.0298292" "Fluorescence Bone Soft Tissue Sarcomas Telomerase"
download_paper "P072" "https://doi.org/10.3390/cancers15082402" "ICG Fluorescence Biopsy Musculoskeletal Tumors"
download_paper "P073" "https://doi.org/10.1002/jso.27306" "NIR ICG Intraoperative Bone Soft Tissue Tumor"
download_paper "P074" "" "Radiologic Osteonecrosis Osteomyelitis CBCT 2023"
download_paper "P075" "https://doi.org/10.1302/0301-620X.105B5.BJJ-2022-0803.R1" "ICG Tumour Residuals Bone Soft Tissue"
download_paper "P076" "https://doi.org/10.3390/diagnostics14010061" "ML Texture Analysis CNO MRI"
download_paper "P077" "https://doi.org/10.1038/s41598-023-32147-w" "Symmetry DL Mastoiditis Detection"
download_paper "P078" "https://doi.org/10.1002/jor.25443" "Open Fracture Fluorescence Bone Perfusion"
download_paper "P079" "https://doi.org/10.1177/01455613211014289" "Moth Eaten Mandible Osteomyelitis"
download_paper "P080" "https://doi.org/10.2460/javma.23.06.0332" "Debridement Jaw Osteomyelitis Rabbits"
download_paper "P081" "https://doi.org/10.3390/ijms24119762" "S aureus Bone Chronic Osteomyelitis Fluorescence"
download_paper "P082" "https://doi.org/10.1016/j.oooo.2021.06.007" "DW MRI Osteomyelitis Mandible"
download_paper "P083" "https://doi.org/10.1007/s00247-021-05270-x" "Automated MRI Bone Marrow Segmentation"
download_paper "P084" "https://doi.org/10.1016/j.urology.2021.10.019" "Robotic Fistula Holmium Laser Debridement"
download_paper "P085" "https://doi.org/10.21873/anticanres.15937" "DL Ewing Sarcoma Osteomyelitis Paediatric"
download_paper "P086" "https://doi.org/10.4045/tidsskr.21.0478" "Osteomyelitis Lower Jaw"
download_paper "P087" "https://doi.org/10.1117/12.2608382" "Dynamic Contrast Fluorescence Bone Perfusion MR"
download_paper "P088" "https://doi.org/10.1097/SLA.0000000000003857" "NIR ICG Bone Soft Tissue Sarcomas Resection"
download_paper "P089" "https://doi.org/10.1007/s11548-021-02474-2" "Automated Mandible Shape Deep Learning"
download_paper "P090" "" "Osteomyelitis Osteoradionecrosis MRONJ CBCT"
download_paper "P091" "https://doi.org/10.1016/j.pdpdt.2020.102003" "Fluorescence MRONJ Jaw Surgery"
download_paper "P092" "https://doi.org/10.1111/odi.13299" "ICG Locate Affected Bone BRONJ"
download_paper "P093" "https://doi.org/10.1371/journal.pone.0241796" "DL Mastoiditis Radiographs"
download_paper "P094" "" "Histopathology Osteomyelitis MRONJ Osteoradionecrosis"
download_paper "P095" "https://doi.org/10.1007/s10143-018-01062-4" "Fluorescence Meningioma Surgery Review"
download_paper "P096" "https://doi.org/10.1002/jbio.201800427" "Bone Kinetic Model ICG Blood Flow"
download_paper "P097" "https://doi.org/10.1007/s00223-018-0495-0" "Chronic Nonbacterial Osteomyelitis Review"
download_paper "P098" "https://doi.org/10.1111/jop.12814" "Chronic Recurrent Osteomyelitis"
download_paper "P099" "" "MRONJ Osteoradionecrosis Osteomyelitis Histopathology"
download_paper "P100" "https://doi.org/10.1016/j.ijom.2016.10.008" "Auto Tetracycline Fluorescence MRONJ Jaw RCT"
download_paper "P101" "https://doi.org/10.1590/1807-3107BOR-2017.vol31.0052" "Periapical Radiopaque Jaw Lesions"

echo ""
echo "=== DOWNLOAD SUMMARY ==="
success_count=$(grep -cE "europepmc|semanticscholar|direct" "$LOG" 2>/dev/null || echo 0)
failed_count=$(grep -c "FAILED" "$LOG" 2>/dev/null || echo 0)
no_doi_count=$(grep -c "NO_DOI" "$LOG" 2>/dev/null || echo 0)
echo "Downloaded: $success_count"
echo "Failed: $failed_count"
echo "No DOI: $no_doi_count"
echo ""
echo "--- Downloaded ---"
grep -E "europepmc|semanticscholar|direct" "$LOG"
echo ""
echo "--- Failed ---"
grep "FAILED" "$LOG"
echo ""
echo "--- No DOI ---"
grep "NO_DOI" "$LOG"
