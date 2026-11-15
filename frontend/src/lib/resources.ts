// Official sources for the kinds of documents GovLens works with.
// Links point to each organisation's own website; they were reachable when this list was written,
// but government sites reorganise and some block automated tools, so treat them as starting points.

export type Region = "India" | "International";

export interface Resource {
  name: string;
  url: string;
  category: string;
  region: Region;
  about: string;
  find: string; // what you can find there
  tip?: string; // how to search it
  slow?: boolean; // reachable, but often slow or blocked from some networks
}

export const CATEGORIES = ["Gazette & law", "Tax & finance", "Regulators", "Ministries", "Parliament & courts", "Commissions & bodies", "Audit & data", "State governments", "United States", "United Kingdom & EU"] as const;

export const RESOURCES: Resource[] = [
  { name: "The Gazette of India (eGazette)", url: "https://egazette.gov.in", category: "Gazette & law", region: "India", about: "The official publication of the Government of India.", find: "Notifications, orders, rules and appointments (S.O., G.S.R.).", tip: "Search by notification number or a date range.", slow: true },
  { name: "India Code", url: "https://www.indiacode.nic.in", category: "Gazette & law", region: "India", about: "Digital repository of central and state Acts.", find: "Acts with their amendments, rules and regulations." },
  { name: "Legislative Department", url: "https://legislative.gov.in", category: "Gazette & law", region: "India", about: "Ministry of Law and Justice, Legislative Department.", find: "Acts, ordinances, bills and Hindi/English versions of laws." },
  { name: "Press Information Bureau", url: "https://pib.gov.in", category: "Gazette & law", region: "India", about: "Official releases from ministries.", find: "Press releases that announce new policies, with links to the full order." },
  { name: "National Portal of India", url: "https://www.india.gov.in", category: "Gazette & law", region: "India", about: "Directory of government websites and services.", find: "Links to every ministry, department and state portal." },

  { name: "CBIC (Customs & GST)", url: "https://www.cbic.gov.in", category: "Tax & finance", region: "India", about: "Central Board of Indirect Taxes and Customs.", find: "GST and customs notifications, circulars and orders.", tip: "Look under Resources, then Notifications or Circulars.", slow: true },
  { name: "GST Portal", url: "https://www.gst.gov.in", category: "Tax & finance", region: "India", about: "The GST system's official site.", find: "GST Acts, rules, notifications and circulars.", tip: "Open Law, then Notifications." },
  { name: "Income Tax Department", url: "https://incometaxindia.gov.in", category: "Tax & finance", region: "India", about: "Central Board of Direct Taxes.", find: "Income-tax notifications, circulars and instructions." },
  { name: "Income Tax e-Filing", url: "https://www.incometax.gov.in", category: "Tax & finance", region: "India", about: "Taxpayer portal.", find: "Latest notifications, forms and guidance." },
  { name: "Department of Financial Services", url: "https://financialservices.gov.in", category: "Tax & finance", region: "India", about: "Banking, insurance and pension policy.", find: "Schemes, circulars and office memoranda." },

  { name: "Reserve Bank of India", url: "https://www.rbi.org.in", category: "Regulators", region: "India", about: "India's central bank and banking regulator.", find: "Master Directions, circulars and notifications.", tip: "Open Notifications, then Master Directions." },
  { name: "SEBI", url: "https://www.sebi.gov.in", category: "Regulators", region: "India", about: "Securities and Exchange Board of India.", find: "Circulars, regulations, orders and consultation papers.", tip: "Use Legal, then Circulars." },
  { name: "IRDAI", url: "https://www.irdai.gov.in", category: "Regulators", region: "India", about: "Insurance regulator.", find: "Regulations, circulars and guidelines." },
  { name: "Ministry of Corporate Affairs", url: "https://www.mca.gov.in", category: "Regulators", region: "India", about: "Company law and LLP administration.", find: "Companies Act notifications, circulars and rules." },

  { name: "DoPT Circulars", url: "https://doptcirculars.nic.in", category: "Ministries", region: "India", about: "Department of Personnel and Training.", find: "Office memoranda and orders on service matters." },
  { name: "Ministry of Labour & Employment", url: "https://labour.gov.in", category: "Ministries", region: "India", about: "Labour law and welfare.", find: "Labour codes, notifications and schemes." },
  { name: "MeitY", url: "https://www.meity.gov.in", category: "Ministries", region: "India", about: "Electronics and Information Technology.", find: "IT rules, policies, notifications and guidelines." },
  { name: "Health & Family Welfare", url: "https://www.mohfw.gov.in", category: "Ministries", region: "India", about: "Public health policy.", find: "Guidelines, advisories and orders." },
  { name: "Ministry of Education", url: "https://www.education.gov.in", category: "Ministries", region: "India", about: "School and higher education.", find: "Policies, circulars and scheme guidelines." },
  { name: "DPIIT", url: "https://www.dpiit.gov.in", category: "Ministries", region: "India", about: "Industry and internal trade.", find: "FDI policy, press notes and startup rules." },

  { name: "Sansad (Parliament of India)", url: "https://sansad.in", category: "Parliament & courts", region: "India", about: "Lok Sabha and Rajya Sabha.", find: "Bills, debates, committee reports and questions." },
  { name: "Supreme Court of India", url: "https://www.sci.gov.in", category: "Parliament & courts", region: "India", about: "Judgments and orders.", find: "Judgments, orders and practice directions." },

  { name: "Comptroller and Auditor General", url: "https://cag.gov.in", category: "Audit & data", region: "India", about: "India's supreme audit institution.", find: "Audit reports tabled in Parliament and state legislatures." },
  { name: "Open Government Data Platform", url: "https://data.gov.in", category: "Audit & data", region: "India", about: "Government datasets and reports.", find: "Datasets, reports and visualisations." },

  { name: "Federal Register", url: "https://www.federalregister.gov", category: "United States", region: "International", about: "Official daily journal of the US government.", find: "Rules, proposed rules and notices.", tip: "Each document has a PDF download link." },
  { name: "GovInfo", url: "https://www.govinfo.gov", category: "United States", region: "International", about: "US Government Publishing Office.", find: "Laws, bills, the Code of Federal Regulations and reports." },
  { name: "Regulations.gov", url: "https://www.regulations.gov", category: "United States", region: "International", about: "Federal rulemaking.", find: "Proposed rules, comments and supporting documents." },

  { name: "UK Legislation", url: "https://www.legislation.gov.uk", category: "United Kingdom & EU", region: "International", about: "The official UK statute database.", find: "Acts and statutory instruments, each downloadable as PDF." },
  { name: "GOV.UK", url: "https://www.gov.uk", category: "United Kingdom & EU", region: "International", about: "Single UK government site.", find: "Policy papers, guidance, consultations and publications." },
  { name: "EUR-Lex", url: "https://eur-lex.europa.eu", category: "United Kingdom & EU", region: "International", about: "Official access to European Union law.", find: "Regulations, directives, decisions and the Official Journal." },

  // ---- More India: law, executive and constitutional bodies ----
  ...india("Gazette & law", [
    ["Ministry of Law and Justice", "https://lawmin.gov.in", "Parent ministry for legislation, justice and company law matters.", "Notifications, reports and Law Commission links."],
    ["Ministry of Home Affairs", "https://www.mha.gov.in", "Internal security, states and disaster management.", "Orders, notifications, advisories and annual reports.", "Open Documents or Notifications."],
    ["Cabinet Secretariat", "https://cabsec.gov.in", "Administrative support to the Union Cabinet.", "Government rules, allocation of business and orders."],
    ["Prime Minister's Office", "https://www.pmindia.gov.in", "Official site of the PMO.", "Speeches, statements and policy announcements."],
    ["MyGov", "https://www.mygov.in", "Citizen engagement platform.", "Consultations on draft policies and rules."],
  ]),
  ...india("Tax & finance", [
    ["Union Budget", "https://www.indiabudget.gov.in", "Budget documents for each year.", "Budget speech, Finance Bill, expenditure and receipts budgets."],
    ["GST Council", "https://www.gstcouncil.gov.in", "Decision body for GST.", "Meeting minutes, press releases and rate decisions."],
    ["DIPAM", "https://dipam.gov.in", "Investment and public asset management.", "Disinvestment policy, notifications and circulars."],
    ["Controller General of Accounts", "https://cga.nic.in", "Government accounting and payments.", "Accounting rules, circulars and monthly accounts."],
    ["DGFT (Foreign Trade)", "https://dgft.gov.in", "Directorate General of Foreign Trade.", "Foreign Trade Policy, notifications, public notices and trade circulars.", "Look under Trade Notices."],
    ["Department of Commerce", "https://commerce.gov.in", "Trade policy and promotion.", "Policies, notifications and trade agreements."],
    ["Department of Economic Affairs", "https://dea.gov.in", "Economic policy, borrowing and the Economic Survey.", "Notifications, reports and the Economic Survey.", undefined, true],
    ["Ministry of Finance", "https://finmin.nic.in", "Union finance ministry.", "Orders, circulars and links to its departments.", undefined, true],
    ["Department of Expenditure", "https://doe.gov.in", "Public spending rules.", "Office memoranda and financial rules.", undefined, true],
  ]),
  ...india("Regulators", [
    ["TRAI", "https://www.trai.gov.in", "Telecom Regulatory Authority of India.", "Regulations, consultation papers and orders."],
    ["IBBI", "https://www.ibbi.gov.in", "Insolvency and Bankruptcy Board of India.", "Regulations, circulars and orders under the IBC."],
    ["Competition Commission of India", "https://www.cci.gov.in", "Competition law regulator.", "Orders, regulations and advisories."],
    ["IFSCA", "https://www.ifsca.gov.in", "International Financial Services Centres Authority.", "Regulations, circulars and framework documents."],
    ["PFRDA", "https://www.pfrda.org.in", "Pension regulator (NPS).", "Regulations, circulars and guidelines."],
    ["EPFO", "https://www.epfindia.gov.in", "Employees' Provident Fund Organisation.", "Circulars, orders and scheme rules."],
    ["ESIC", "https://www.esic.gov.in", "Employees' State Insurance Corporation.", "Circulars, regulations and scheme details."],
    ["FSSAI", "https://fssai.gov.in", "Food Safety and Standards Authority.", "Food safety regulations, orders and advisories."],
    ["CDSCO", "https://cdsco.gov.in", "Central drugs regulator.", "Drug and device rules, notices and guidelines."],
    ["PNGRB", "https://www.pngrb.gov.in", "Petroleum and Natural Gas Regulatory Board.", "Regulations, orders and notifications."],
    ["Bureau of Indian Standards", "https://www.bis.gov.in", "National standards body.", "Standards, certification rules and notifications."],
    ["DGCA", "https://www.dgca.gov.in", "Civil aviation regulator.", "Civil Aviation Requirements, circulars and orders."],
    ["NHAI", "https://nhai.gov.in", "National Highways Authority of India.", "Policy circulars, tenders and guidelines."],
    ["NCLT", "https://nclt.gov.in", "National Company Law Tribunal.", "Orders and cause lists for company law cases."],
    ["NCLAT", "https://nclat.nic.in", "National Company Law Appellate Tribunal.", "Appeal orders and judgments."],
  ]),
  ...india("Ministries", [
    ["Ministry of External Affairs", "https://www.mea.gov.in", "Foreign relations.", "Treaties, agreements and press releases."],
    ["Ministry of Defence", "https://www.mod.gov.in", "Defence policy.", "Policies, procurement procedure and annual reports."],
    ["Road Transport & Highways", "https://morth.nic.in", "Roads, vehicles and motor-vehicle rules.", "Notifications, circulars and the Motor Vehicles Act rules."],
    ["Environment, Forest & Climate Change", "https://moef.gov.in", "Environmental policy and regulation.", "Environment notifications, rules and clearances guidance."],
    ["PARIVESH", "https://parivesh.nic.in", "Environmental and forest clearance portal.", "Clearance records, guidelines and office memoranda."],
    ["Agriculture & Farmers Welfare", "https://agriwelfare.gov.in", "Farm policy and schemes.", "Scheme guidelines, orders and notifications."],
    ["Renewable Energy (MNRE)", "https://mnre.gov.in", "Solar, wind and other renewables.", "Policies, guidelines and notifications."],
    ["Ministry of Mines", "https://mines.gov.in", "Mining policy.", "Mineral rules, notifications and guidelines."],
    ["Ministry of Steel", "https://steel.gov.in", "Steel sector policy.", "Schemes, policies and orders."],
    ["Ministry of Tourism", "https://tourism.gov.in", "Tourism promotion.", "Scheme guidelines and policies."],
    ["Indian Railways", "https://indianrailways.gov.in", "Railway Board and zones.", "Railway Board circulars, orders and rules."],
    ["Civil Aviation", "https://civilaviation.gov.in", "Aviation policy.", "Policies, rules and notifications."],
    ["Ports, Shipping & Waterways", "https://shipmin.gov.in", "Maritime policy.", "Acts, rules and notifications."],
    ["Rural Development", "https://rural.gov.in", "Rural schemes such as MGNREGA and PMAY-G.", "Guidelines, circulars and scheme orders."],
    ["Housing & Urban Affairs", "https://mohua.gov.in", "Cities and housing.", "Scheme guidelines and urban policy documents."],
    ["Social Justice & Empowerment", "https://socialjustice.gov.in", "Welfare of disadvantaged groups.", "Scheme guidelines, acts and orders."],
    ["Minority Affairs", "https://www.minorityaffairs.gov.in", "Welfare of minority communities.", "Scheme guidelines and orders."],
    ["Atomic Energy", "https://dae.gov.in", "Department of Atomic Energy.", "Policies, annual reports and orders."],
    ["Science & Technology", "https://dst.gov.in", "Department of Science and Technology.", "Programmes, policies and calls."],
    ["Water Resources (Jal Shakti)", "https://jalshakti-dowr.gov.in", "Water resources and river development.", "Policies, guidelines and reports."],
    ["UGC", "https://www.ugc.gov.in", "University Grants Commission.", "Regulations, notices and guidelines for universities."],
    ["CBSE", "https://www.cbse.gov.in", "Central Board of Secondary Education.", "Circulars, curriculum and examination notices."],
  ]),
  ...india("Parliament & courts", [
    ["eCourts Services", "https://ecourts.gov.in", "Court case information across India.", "Case status and orders for district courts and high courts."],
    ["eCourts Judgments", "https://judgments.ecourts.gov.in", "Searchable judgments of high courts and district courts.", "Judgments and orders as PDFs.", "Search by case number or keyword."],
    ["Delhi High Court", "https://delhihighcourt.nic.in", "Judgments, orders and notices.", "Judgments, cause lists and circulars."],
    ["Allahabad High Court", "https://www.allahabadhighcourt.in", "Judgments, orders and notices.", "Judgments and notices."],
    ["Lok Sabha", "https://loksabha.nic.in", "Lower house of Parliament.", "Bills, debates and questions.", undefined, true],
    ["Rajya Sabha", "https://rajyasabha.nic.in", "Upper house of Parliament.", "Bills, debates and committee reports.", undefined, true],
    ["Bombay High Court", "https://bombayhighcourt.nic.in", "Judgments, orders and notices.", "Judgments and circulars.", undefined, true],
  ]),
  ...india("Commissions & bodies", [
    ["NITI Aayog", "https://www.niti.gov.in", "Government's policy think tank.", "Policy reports, strategy papers and indices."],
    ["Election Commission of India", "https://eci.gov.in", "Conducts elections.", "Orders, notifications, manuals and rules."],
    ["Central Information Commission", "https://cic.gov.in", "Right to Information appeals.", "RTI decisions, orders and guidelines."],
    ["Central Vigilance Commission", "https://cvc.gov.in", "Anti-corruption body.", "Circulars, guidelines and vigilance manuals."],
    ["UPSC", "https://www.upsc.gov.in", "Union Public Service Commission.", "Notifications, rules and exam notices."],
    ["Staff Selection Commission", "https://ssc.gov.in", "Government recruitment.", "Notices and recruitment rules."],
    ["NHRC", "https://nhrc.nic.in", "National Human Rights Commission.", "Guidelines, advisories and reports."],
    ["UIDAI (Aadhaar)", "https://uidai.gov.in", "Aadhaar authority.", "Regulations, circulars and notifications."],
    ["CERT-In", "https://www.cert-in.org.in", "National cyber security agency.", "Directions, advisories and guidelines."],
    ["Government e-Marketplace (GeM)", "https://gem.gov.in", "Public procurement marketplace.", "Procurement rules, orders and GeM policy documents."],
    ["Central Public Procurement Portal", "https://eprocure.gov.in", "Tenders by central departments.", "Tender notices and procurement documents."],
  ]),
  ...india("Audit & data", [
    ["Ministry of Statistics (MoSPI)", "https://www.mospi.gov.in", "Official statistics.", "Statistical reports, surveys and publications."],
    ["Census of India", "https://censusindia.gov.in", "Population data.", "Census reports and tables."],
  ]),
  ...india("State governments", [
    ["Maharashtra", "https://www.maharashtra.gov.in", "State portal.", "Government resolutions (GRs), notifications and departments."],
    ["Tamil Nadu", "https://www.tn.gov.in", "State portal.", "Government orders (G.O.), policies and departments."],
    ["Delhi", "https://delhi.gov.in", "State portal.", "Orders, notifications and department sites."],
    ["Uttar Pradesh", "https://up.gov.in", "State portal.", "Government orders and department links."],
    ["Gujarat", "https://gujaratindia.gov.in", "State portal.", "Resolutions, policies and departments."],
    ["West Bengal", "https://wb.gov.in", "State portal.", "Notifications, orders and department links."],
    ["Kerala", "https://kerala.gov.in", "State portal.", "Government orders and department links."],
    ["Rajasthan", "https://rajasthan.gov.in", "State portal.", "Orders, policies and department links."],
    ["Telangana", "https://www.telangana.gov.in", "State portal.", "Government orders and department links."],
    ["Andhra Pradesh", "https://www.ap.gov.in", "State portal.", "Government orders and department links."],
    ["Haryana", "https://haryana.gov.in", "State portal.", "Notifications, orders and departments."],
    ["Odisha", "https://odisha.gov.in", "State portal.", "Resolutions, notifications and departments."],
    ["Assam", "https://assam.gov.in", "State portal.", "Notifications and department links."],
    ["Jharkhand", "https://jharkhand.gov.in", "State portal.", "Orders and department links."],
    ["Chhattisgarh", "https://cgstate.gov.in", "State portal.", "Orders and department links."],
    ["Himachal Pradesh", "https://hp.gov.in", "State portal.", "Notifications and department links."],
    ["Goa", "https://goa.gov.in", "State portal.", "Notifications and department links."],
  ]),
];

type Row = [name: string, url: string, about: string, find: string, tip?: string, slow?: boolean];
function india(category: string, rows: Row[]): Resource[] {
  return rows.map(([name, url, about, find, tip, slow]) => ({ name, url, category, region: "India" as const, about, find, tip, slow }));
}

export const SEARCH_EXAMPLES = [
  { label: "A GST notification", query: 'site:cbic.gov.in notification 12/2023 filetype:pdf' },
  { label: "An RBI master direction", query: 'site:rbi.org.in "master direction" filetype:pdf' },
  { label: "A SEBI circular", query: 'site:sebi.gov.in circular 2024 filetype:pdf' },
  { label: "Any ministry order", query: 'site:gov.in "order no" 2024 filetype:pdf' },
  { label: "A state government order (G.O.)", query: 'site:tn.gov.in "G.O." 2024 filetype:pdf' },
  { label: "A court judgment", query: 'site:ecourts.gov.in judgment "section 138" filetype:pdf' },
  { label: "An income-tax circular", query: 'site:incometaxindia.gov.in circular 2024 filetype:pdf' },
  { label: "A parliamentary committee report", query: 'site:sansad.in "standing committee" report filetype:pdf' },
];
