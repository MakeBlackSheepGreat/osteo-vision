const https = require('https');
const http = require('http');
const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

const OUTDIR = 'C:/Users/876762330/Desktop/projects/osteo-vision/output/literature/papers';

const remaining = [
  {id:'P056', doi:'10.1016/j.idc.2025.02.015', title:'Jaw Osteomyelitis'},
  {id:'P057', doi:'10.2106/JBJS.24.01436', title:'Intraoperative Bone Perfusion Fluorescence'},
  {id:'P058', doi:'10.1007/s00223-025-01354-0', title:'Bisphosphonates Nonbacterial Osteomyelitis Mandible'},
  {id:'P060', doi:'10.12200/j.issn.1003-0034.20240445', title:'Imaging Techniques Chronic Osteomyelitis'},
  {id:'P061', doi:'10.1016/j.suronc.2024.102091', title:'NIR ICG Bone Soft Tissue Tumours'},
  {id:'P063', doi:'10.17116/stomat202410306173', title:'Chronic Osteomyelitis Mandible Children'},
  {id:'P066', doi:'10.1093/dmfr/twae028', title:'Multiclass Jaw Lesions CBCT DL'},
  {id:'P067', doi:null, title:'Radiologic Osteonecrosis Osteomyelitis CBCT 2024'},
  {id:'P068', doi:'10.1016/j.amjoto.2024.104343', title:'ICG Landmark Arteries Sinus'},
  {id:'P073', doi:'10.1002/jso.27306', title:'NIR ICG Bone Soft Tissue Tumor Surgery'},
  {id:'P074', doi:null, title:'Radiologic Osteonecrosis CBCT 2023'},
  {id:'P075', doi:'10.1302/0301-620X.105B5.BJJ-2022-0803.R1', title:'ICG Tumour Residuals Bone'},
  {id:'P078', doi:'10.1002/jor.25443', title:'Open Fracture Fluorescence Bone Perfusion'},
  {id:'P079', doi:'10.1177/01455613211014289', title:'Moth Eaten Mandible Osteomyelitis'},
  {id:'P080', doi:'10.2460/javma.23.06.0332', title:'Debridement Jaw Osteomyelitis'},
  {id:'P082', doi:'10.1016/j.oooo.2021.06.007', title:'DW MRI Osteomyelitis Mandible'},
  {id:'P084', doi:'10.1016/j.urology.2021.10.019', title:'Robotic Fistula Debridement'},
  {id:'P085', doi:'10.21873/anticanres.15937', title:'DL Ewing Sarcoma Osteomyelitis'},
  {id:'P086', doi:'10.4045/tidsskr.21.0478', title:'Osteomyelitis Lower Jaw'},
  {id:'P087', doi:'10.1117/12.2608382', title:'Dynamic Contrast Fluorescence Bone'},
  {id:'P088', doi:'10.1097/SLA.0000000000003857', title:'NIR ICG Bone Sarcomas'},
  {id:'P090', doi:null, title:'Osteomyelitis MRONJ CBCT'},
  {id:'P091', doi:'10.1016/j.pdpdt.2020.102003', title:'Fluorescence MRONJ Jaw'},
  {id:'P092', doi:'10.1111/odi.13299', title:'ICG Locate Bone BRONJ'},
  {id:'P094', doi:null, title:'Histopathology Osteomyelitis MRONJ'},
  {id:'P096', doi:'10.1002/jbio.201800427', title:'Bone Kinetic Model ICG'},
  {id:'P097', doi:'10.1007/s00223-018-0495-0', title:'Chronic Nonbacterial Osteomyelitis'},
  {id:'P098', doi:'10.1111/jop.12814', title:'Chronic Recurrent Osteomyelitis'},
  {id:'P099', doi:null, title:'MRONJ Osteoradionecrosis Histopathology'},
  {id:'P100', doi:'10.1016/j.ijom.2016.10.008', title:'Auto Fluorescence MRONJ Jaw'},
  {id:'P101', doi:'10.1590/1807-3107BOR-2017.vol31.0052', title:'Periapical Jaw Lesions'},
];

const results = {ok:[], fail:[]};

function safeName(paper) {
  const safe = paper.title.replace(/[^a-zA-Z0-9]/g,'_').substring(0,60);
  return paper.id + '_' + safe + '.pdf';
}

function fetchUrl(url, maxRedirects) {
  if (maxRedirects === undefined) maxRedirects = 5;
  return new Promise(function(resolve, reject) {
    if (maxRedirects <= 0) return reject(new Error('Too many redirects'));
    var proto = url.startsWith('https') ? https : http;
    var req = proto.get(url, {
      headers: {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'application/pdf,*/*',
      },
      timeout: 30000,
    }, function(res) {
      if (res.statusCode >= 300 && res.statusCode < 400 && res.headers.location) {
        var loc = res.headers.location;
        if (!loc.startsWith('http')) {
          try { loc = new URL(loc, url).href; } catch(e) { return reject(new Error('bad redirect')); }
        }
        return fetchUrl(loc, maxRedirects-1).then(resolve).catch(reject);
      }
      if (res.statusCode !== 200) return reject(new Error('HTTP ' + res.statusCode));
      var chunks = [];
      res.on('data', function(c) { chunks.push(c); });
      res.on('end', function() { resolve(Buffer.concat(chunks)); });
      res.on('error', reject);
    });
    req.on('error', reject);
    req.on('timeout', function() { req.destroy(); reject(new Error('timeout')); });
  });
}

function curlFetch(url) {
  try {
    return execSync('curl -sL --max-time 20 "' + url + '"', {encoding:'utf8', timeout:25000});
  } catch(e) { return ''; }
}

async function tryDownload(paper) {
  var outfile = path.join(OUTDIR, safeName(paper));
  if (fs.existsSync(outfile) && fs.statSync(outfile).size > 10000) {
    var hdr = fs.readFileSync(outfile).slice(0,5).toString();
    if (hdr.indexOf('%PDF') >= 0) { results.ok.push({id:paper.id, via:'exists'}); return; }
  }

  // Strategy 1: EuropePMC
  if (paper.doi) {
    try {
      var epmcJson = curlFetch('https://www.ebi.ac.uk/europepmc/webservices/rest/search?query=DOI:' + paper.doi + '&format=json');
      var pmcidMatch = epmcJson.match(/"pmcid":"(PMC\d+)"/);
      if (pmcidMatch) {
        var data = await fetchUrl('https://europepmc.org/api/getPdf?pmcid=' + pmcidMatch[1]);
        if (data.length > 10000 && data.slice(0,5).toString().indexOf('%PDF') >= 0) {
          fs.writeFileSync(outfile, data);
          results.ok.push({id:paper.id, via:'europepmc'});
          return;
        }
      }
    } catch(e) {}
  }

  // Strategy 2: Semantic Scholar
  if (paper.doi) {
    try {
      var ssJson = curlFetch('https://api.semanticscholar.org/graph/v1/paper/DOI:' + paper.doi + '?fields=openAccessPdf');
      var urlMatch = ssJson.match(/"url":"(https?:\/\/[^"]+)"/);
      if (urlMatch && urlMatch[1].indexOf('null') < 0) {
        var data = await fetchUrl(urlMatch[1]);
        if (data.length > 10000 && data.slice(0,5).toString().indexOf('%PDF') >= 0) {
          fs.writeFileSync(outfile, data);
          results.ok.push({id:paper.id, via:'semanticscholar'});
          return;
        }
      }
    } catch(e) {}
  }

  // Strategy 3: Publisher direct
  if (paper.doi) {
    var d = paper.doi;
    var urls = [];

    if (d.indexOf('10.3390/') === 0) {
      urls.push('https://www.mdpi.com/' + d.replace('10.3390/','') + '/pdf');
    }
    if (d.indexOf('10.3389/') === 0) {
      var parts = d.split('/');
      urls.push('https://www.frontiersin.org/journals/' + parts[1] + '/articles/' + d + '/pdf');
    }
    if (d.indexOf('10.1007/') === 0 || d.indexOf('10.1186/') === 0) {
      urls.push('https://link.springer.com/content/pdf/' + d + '.pdf');
    }
    if (d.indexOf('10.1038/') === 0) {
      urls.push('https://www.nature.com/articles/' + d.replace('10.1038/','') + '.pdf');
    }
    if (d.indexOf('10.1371/') === 0) {
      urls.push('https://journals.plos.org/plosone/article/file?id=' + d + '&type=printable');
    }
    if (d.indexOf('10.1177/') === 0) {
      urls.push('https://journals.sagepub.com/doi/pdf/' + d);
    }
    if (d.indexOf('10.1002/') === 0 || d.indexOf('10.1111/') === 0) {
      urls.push('https://onlinelibrary.wiley.com/doi/pdfdirect/' + d);
    }
    if (d.indexOf('10.1016/') === 0) {
      var pii = d.replace('10.1016/','').split('/').pop().split('.')[0];
      urls.push('https://www.sciencedirect.com/science/article/pii/' + pii + '/pdfft');
    }
    // Wolters Kluwer - try via PMC
    if (d.indexOf('10.1097/') === 0 || d.indexOf('10.2106/') === 0 || d.indexOf('10.21873/') === 0) {
      try {
        var epmcJson2 = curlFetch('https://www.ebi.ac.uk/europepmc/webservices/rest/search?query=DOI:' + d + '&format=json');
        var pmcid2 = epmcJson2.match(/"pmcid":"(PMC\d+)"/);
        if (pmcid2) {
          urls.unshift('https://europepmc.org/api/getPdf?pmcid=' + pmcid2[1]);
        }
      } catch(e) {}
    }
    // SPIE
    if (d.indexOf('10.1117/') === 0) {
      urls.push('https://www.spiedigitallibrary.org/conference-proceedings-of-spie/' + d.replace('10.1117/12.','') + '.full');
    }
    // Scielo (Brazilian journals)
    if (d.indexOf('10.1590/') === 0) {
      urls.push('https://www.scielo.br/j/bor/a/' + d.replace('10.1590/','') + '/?format=pdf&lang=en');
    }

    for (var i = 0; i < urls.length; i++) {
      try {
        var data = await fetchUrl(urls[i]);
        if (data.length > 10000 && data.slice(0,5).toString().indexOf('%PDF') >= 0) {
          fs.writeFileSync(outfile, data);
          results.ok.push({id:paper.id, via:'direct'});
          return;
        }
      } catch(e) {}
    }
  }

  results.fail.push({id:paper.id, doi:paper.doi || 'none'});
}

(async function() {
  console.log('Downloading ' + remaining.length + ' remaining papers...');
  for (var i = 0; i < remaining.length; i++) {
    var p = remaining[i];
    process.stdout.write('[' + (i+1) + '/' + remaining.length + '] ' + p.id + '...');
    await tryDownload(p);
    var last = results.ok.length > 0 ? results.ok[results.ok.length-1] : null;
    var lastF = results.fail.length > 0 ? results.fail[results.fail.length-1] : null;
    if (last && last.id === p.id) {
      console.log(' OK via ' + last.via);
    } else if (lastF && lastF.id === p.id) {
      console.log(' FAILED');
    } else {
      console.log(' SKIP');
    }
  }

  console.log('\n=== DOWNLOAD RESULTS ===');
  console.log('Downloaded: ' + results.ok.length);
  console.log('Failed: ' + results.fail.length);
  console.log('\nDownloaded:');
  results.ok.forEach(function(r) { console.log('  ' + r.id + ' via ' + r.via); });
  console.log('\nFailed (need manual search):');
  results.fail.forEach(function(r) { console.log('  ' + r.id + ' (' + r.doi + ')'); });
})();
