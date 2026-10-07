"""Starter wording for the procedures a KEBS packaged-drinking-water application
expects to see documented. Loaded once by migration 0002 as DRAFTS — they are a
reasoned starting point, not a finished legal document: management must read each
one, adjust it to how the plant really operates (job titles, frequencies, the actual
pest-control contractor, and so on) and then approve it in the Procedures screen.

Formatting is the lightweight markup rendered by compliance_tags.procedure_body."""

from .models import Procedure

PROCEDURES = [
    {
        "code": "SOP-001",
        "title": "Product Recall Procedure",
        "category": Procedure.RECALL,
        "owner": "Managing Director",
        "content": """## 1. Purpose
To remove promptly from the market any Fontis Springs product that is, or may be, unsafe or does not conform to KS EAS 153:2018 (Packaged Drinking Water) or KS EAS 38:2014 (Labelling), and to protect consumers while doing so.

## 2. Scope
All packaged drinking water and refills produced, stored or distributed by Fontis Springs, including stock already delivered to customers and distributors.

## 3. Responsibilities
| Role | Responsibility |
| --- | --- |
| Managing Director | Authorises a recall, signs the notification to KEBS and the public health authority, owns this procedure |
| Production Manager | Locates and quarantines affected stock, supplies batch and production records |
| Quality Controller | Assesses the hazard, decides the batches affected, leads the root-cause investigation |
| Sales / Dispatch Supervisor | Identifies every customer who received the affected batches and contacts them |
| Customer Care Officer | Handles customer calls and records returns |

## 4. Traceability
- Every container is coded with a batch code and production date so a finished product can be traced to its production run, its raw materials and its quality-control records.
- Dispatch records (the Sales module) show which customers received which products on which dates, so affected customers can be listed within hours.
- Quality-control and laboratory records for each batch are kept as set out in the Quality Control Procedure (SOP-007).

## 5. Situations that trigger a recall review
- A finished-product or retained-sample test fails KS EAS 153:2018 requirements.
- Contamination, a foreign body or a processing failure is found after product has left the premises.
- A customer complaint, or a pattern of complaints, suggests illness or a safety defect (see SOP-002).
- A labelling error that could mislead or endanger consumers, such as a wrong date code or a missing required declaration.
- A notice from KEBS, the public health authority or a supplier of materials found to be unsafe.

## 6. Procedure
1. **Stop and hold.** Whoever discovers the problem immediately stops dispatch of the suspect product and informs the Quality Controller and Production Manager.
2. **Assess.** The Quality Controller assesses the hazard and the batches involved using production, laboratory and dispatch records, and reports to the Managing Director the same day.
3. **Decide.** The Managing Director decides whether to recall, the scope (which batches, which dates) and the urgency. If in doubt, recall.
4. **Notify the authorities.** The Managing Director informs KEBS and the public health authority, giving the product, batch codes, nature of the hazard, quantities and the action being taken.
5. **Notify customers.** The Dispatch Supervisor lists every customer who received the affected batches and contacts them by telephone and SMS (CRM module) with clear instructions: stop using or selling the product, keep it aside, and how it will be collected.
6. **Retrieve.** Affected product is collected, counted against the quantity dispatched, and stored in a marked, locked quarantine area. Returns are recorded in the recall log below.
7. **Reconcile.** Compare quantity produced, quantity sold, quantity recovered and quantity still in stock. Investigate any unexplained difference.
8. **Decide the fate of recalled product.** Destroy it, or reprocess it only if the Quality Controller confirms in writing that it can be made safe and compliant. Destruction is witnessed and recorded (see SOP-004).
9. **Investigate and correct.** Find the root cause, record corrective and preventive actions with owners and dates, and verify they work before normal production resumes for the affected line.
10. **Close out.** The Managing Director signs a recall report summarising events, quantities, communications, root cause and actions, and files it with the recall log.

## 7. Recall test
At least once a year a mock recall is carried out on a real batch to prove traceability works. The target is to trace the batch to its raw materials and to every customer who received it within four hours. Results and any weaknesses found are recorded and corrected.

## 8. Recall log
| Date | Product / batch | Reason | Quantity produced | Quantity recovered | Authorities notified | Closed by |
| --- | --- | --- | --- | --- | --- | --- |
|  |  |  |  |  |  |  |

## 9. Records and review
Recall reports, the recall log, notifications and test results are kept for at least two years. This procedure is reviewed every year and after any recall or mock recall.
""",
    },
    {
        "code": "SOP-002",
        "title": "Customer Complaint Handling Procedure",
        "category": Procedure.COMPLAINT,
        "owner": "Quality Controller",
        "content": """## 1. Purpose
To make sure every complaint about Fontis Springs products or service is recorded, investigated, answered and used to improve, and that any complaint with a safety implication reaches management immediately.

## 2. Scope
Complaints received from customers, distributors, delivery staff or the public by any route: telephone, SMS, walk-in, social media or through a delivery driver.

## 3. Responsibilities
| Role | Responsibility |
| --- | --- |
| Customer Care Officer | Receives and records the complaint, acknowledges it, keeps the customer informed |
| Quality Controller | Investigates quality and safety complaints, decides corrective action |
| Production Manager | Supplies batch and production records, carries out corrective action |
| Managing Director | Receives escalated safety complaints, reviews complaint trends |

## 4. Procedure
1. **Receive and record.** Record every complaint on the same day in the CRM module (Complaints): customer, date, product, batch or delivery date if known, and what the customer says happened. Do not argue or assign blame at this stage.
2. **Acknowledge.** Thank the customer and acknowledge the complaint within 24 hours, explaining who will follow up and by when.
3. **Classify.** Mark the complaint as one of: product quality or safety, packaging or labelling, delivery, or service and billing.
4. **Escalate safety complaints at once.** Any complaint involving illness, a foreign body, taste or smell, or visible contamination is passed to the Quality Controller and the Managing Director immediately, and the remaining stock of that batch is put on hold until assessed. Consider SOP-001 (Product Recall).
5. **Collect evidence.** Where possible, collect the product or container from the customer and keep it, labelled with the complaint number.
6. **Investigate.** The Quality Controller checks the batch code against production records, retained samples, laboratory results and hygiene records, tests the returned sample if appropriate, and determines the cause.
7. **Respond.** Give the customer a clear answer on the findings and what has been done, normally within seven days. Replace or refund product where the complaint is justified.
8. **Correct.** Where the cause is on our side, record a corrective action with an owner and a due date, and confirm it has been completed.
9. **Close.** Close the complaint in the CRM module only when the customer has been answered and any action is done.

## 5. Monitoring
- Complaints are reviewed monthly by management: count, type, batches and products involved, time taken to respond.
- A repeat complaint about the same batch, product or cause triggers a formal investigation and, where relevant, a review of this procedure and of SOP-007.

## 6. Records and review
The CRM complaints register, investigation notes and customer responses are kept for at least two years. This procedure is reviewed every year.
""",
    },
    {
        "code": "SOP-003",
        "title": "Pest Control Management Procedure",
        "category": Procedure.PEST,
        "owner": "Production Manager",
        "content": """## 1. Purpose
To keep rodents, insects, birds and other pests out of the production, storage and surrounding areas so that product and packaging are never exposed to contamination.

## 2. Scope
The whole Fontis Springs compound: production hall, filling area, stores for bottles, caps and labels, finished-goods store, water storage, offices, washrooms, drains and external grounds.

## 3. Responsibilities
| Role | Responsibility |
| --- | --- |
| Production Manager | Owns the programme, engages the contractor, reviews reports, makes sure findings are fixed |
| Hygiene Supervisor | Daily visual checks, keeps the sightings log, housekeeping |
| Pest control contractor | Licensed operator who services the premises and issues a signed service report |
| All staff | Report any sign of pests immediately and keep their areas clean |

## 4. Prevention (proofing and housekeeping)
- Doors, windows and vents are kept closed or fitted with screens; door gaps and wall openings are sealed.
- Drains are covered and kept clean; there is no standing water outside the plant.
- Waste is removed daily and bins kept closed (see SOP-004). No food is eaten or stored in the production area.
- Materials are stored off the floor and away from walls so inspection and cleaning are possible.
- Grass and vegetation around the building are kept short and clear of the walls.

## 5. Control programme
1. A licensed pest control company is contracted to service the premises at least monthly, or more often if the contractor recommends it.
2. The contractor supplies a site map showing the position of every bait station and trap, each numbered, and updates it when stations move.
3. Only pesticides approved for use in food premises are used, and never inside the production hall during production or where open product or packaging is exposed. No pesticide is stored on site except in the contractor's locked kit.
4. After every visit the contractor leaves a signed service report stating the work done, chemicals used, findings and recommendations.
5. The contractor's licence or certificate and a current list of chemicals used are kept on file.

## 6. Daily checks and sightings
1. The Hygiene Supervisor walks the premises each day looking for droppings, gnaw marks, insects, birds and damaged proofing, and checks that bait stations are intact.
2. Any sighting is recorded in the log below and reported to the Production Manager the same day; serious activity is reported to the contractor for an extra visit.
3. Product or packaging that may have been contaminated is placed on hold until the Quality Controller has assessed it.

## 7. Corrective action
Findings from the contractor's report or daily checks are listed with an action, an owner and a date, and signed off once fixed. Repeated findings in the same place lead to a review of the proofing.

## 8. Sightings log
| Date | Area | What was seen | Action taken | Reported to contractor | Closed by |
| --- | --- | --- | --- | --- | --- |
|  |  |  |  |  |  |

## 9. Records and review
Service reports, the site map, the contractor's licence, the sightings log and corrective-action records are kept for at least two years. This procedure is reviewed every year.
""",
    },
    {
        "code": "SOP-004",
        "title": "Waste Management Procedure",
        "category": Procedure.WASTE,
        "owner": "Production Manager",
        "content": """## 1. Purpose
To collect, store and dispose of every kind of waste produced by Fontis Springs safely, in a way that never contaminates product, and in line with public health and environmental requirements.

## 2. Scope
Solid waste, rejected packaging and product, used filter media, laboratory waste, wastewater and general rubbish from production, laboratory, offices and washrooms.

## 3. Waste streams and how each is handled
| Waste | Where it comes from | Handling | Disposal |
| --- | --- | --- | --- |
| General waste | Offices, canteen area, washrooms | Closed bins, emptied daily | Licensed waste collector or county service |
| Recyclable plastics | Rejected bottles and caps, shrink wrap, offcuts | Separate marked bin or cage, away from production | Sold or given to a registered recycler |
| Rejected or recalled product | Failed QC, damaged, expired or recalled stock | Held in quarantine, labelled, then destroyed under witness | Emptied to drain and packaging recycled or disposed of as above |
| Used filter cartridges and media | Water treatment | Bagged and removed from the production area | Licensed waste collector |
| Laboratory waste | Test reagents, used sample containers | Kept in labelled containers in the laboratory | Disposed of as the reagent supplier directs |
| Wastewater | Reject water, backwash, cleaning water | Drained away from the building through covered drains | Sewer or licensed disposal route, in line with local authority and NEMA requirements |

## 4. Rules
- Waste bins are clearly marked, have lids, are lined, and are never placed where they could contaminate product or packaging.
- Waste is removed from the production area at least daily and at the end of every shift, and never carried through clean areas while product is exposed.
- The waste holding area is outside the production building, kept clean and tidy, and cleared regularly.
- Chemicals and used chemical containers are never reused for water or product.
- Only a licensed or authorised collector removes waste, and a receipt or collection record is obtained.

## 5. Destruction of rejected or expired product
1. The Quality Controller authorises destruction in writing, stating product, batch and quantity.
2. Destruction is done in the presence of a second person, who signs the record.
3. Containers are emptied, defaced so they cannot be reused or resold, and the packaging is disposed of or recycled as above.

## 6. Waste log
| Date | Type of waste | Quantity | Disposal method | Collector / witness | Receipt no. | Signed |
| --- | --- | --- | --- | --- | --- | --- |
|  |  |  |  |  |  |  |

## 7. Records and review
The waste log, destruction records and collector receipts are kept for at least two years. This procedure is reviewed every year.
""",
    },
    {
        "code": "SOP-005",
        "title": "Cleaning, Sanitation and Hygiene Schedule",
        "category": Procedure.HYGIENE,
        "owner": "Hygiene Supervisor",
        "content": """## 1. Purpose
To keep the premises, equipment and vehicles clean and sanitary so that product is never contaminated.

## 2. Scope
Production hall, filling and capping area, water storage, laboratory, stores, washrooms, hand-wash points, foot bath and delivery vehicles.

## 3. Cleaning chemicals
- Only cleaners and sanitisers suitable for food and drinking-water premises are used, at the strength given on the supplier's label.
- Chemicals are kept in a locked, labelled store away from product and packaging, and are never decanted into drink containers.
- Equipment is rinsed with potable water after sanitising so no residue remains.

## 4. Cleaning schedule
| Area / item | What is done | Frequency | Responsible | Checked by |
| --- | --- | --- | --- | --- |
| Production hall floors and drains | Sweep, wash, disinfect | Daily, end of shift | Cleaner | Hygiene Supervisor |
| Filling and capping machine | Clean and sanitise contact parts; rinse | Before starting and at end of each day | Machine operator | Quality Controller |
| Stainless steel tables and work surfaces | Wash, sanitise | Before use and between tasks | Production staff | Hygiene Supervisor |
| Water storage tanks | Drain, scrub, sanitise, rinse | At the interval set by the Quality Controller, and after any contamination | Technician | Quality Controller |
| Filters, membranes and cartridges | Inspect, backwash or replace | Per the maintenance plan | Technician | Production Manager |
| Hand-wash points | Clean, restock soap and hand-drying means | Daily | Cleaner | Hygiene Supervisor |
| Foot bath | Empty, refill with fresh solution | Daily | Cleaner | Hygiene Supervisor |
| Washrooms | Clean and disinfect | Twice daily | Cleaner | Hygiene Supervisor |
| Laboratory benches | Wipe and sanitise | Daily | Laboratory technician | Quality Controller |
| Stores | Sweep, clear litter, check stock off the floor | Weekly | Storekeeper | Production Manager |
| Delivery vehicles (load area) | Wash and sanitise | Weekly | Driver | Dispatch Supervisor |
| Walls, ceilings and fittings | Clean | Monthly | Cleaner | Production Manager |

## 5. Method for cleaning equipment
1. Remove product and loose debris.
2. Wash with detergent and potable water.
3. Rinse with potable water.
4. Sanitise at the correct strength for the contact time on the label.
5. Rinse with potable water and allow to drain and dry. Do not use dirty cloths for drying.

## 6. Verification
- The Hygiene Supervisor signs the daily checklist after inspecting each item.
- The Quality Controller inspects the premises and tests the effectiveness of cleaning at the frequency set in SOP-007, for example a rinse-water test from cleaned filling equipment.
- Any area found unsatisfactory is cleaned again and the reason recorded.

## 7. Daily hygiene checklist
| Date | Hall and drains | Filling machine | Tables | Hand-wash point stocked | Foot bath refilled | Washrooms | Supervisor signature |
| --- | --- | --- | --- | --- | --- | --- | --- |
|  |  |  |  |  |  |  |  |

## 8. Records and review
Completed checklists and verification records are kept for at least two years. This schedule is reviewed every year.
""",
    },
    {
        "code": "SOP-006",
        "title": "Personal Hygiene, Medical Fitness and Protective Clothing",
        "category": Procedure.PERSONAL_HYGIENE,
        "owner": "Production Manager",
        "content": """## 1. Purpose
To make sure people who handle product or work in the production area cannot contaminate it, and are medically fit to do so.

## 2. Scope
All employees, casual workers, contractors and visitors who enter the production, filling, laboratory or storage areas.

## 3. Medical fitness
1. Every food handler must hold a valid medical certificate, as required under the Public Health Act (Cap 254), before starting work and must keep it valid for as long as they handle product.
2. Certificates are recorded in the Compliance module (Medical Certificates). The system warns 30 days before one expires; the renewal examination is arranged before the expiry date.
3. A person without a valid certificate does not work in the production area.
4. Staff must tell their supervisor at once if they have diarrhoea, vomiting, fever, a sore throat with fever, jaundice, or infected skin sores or discharge from the ear, eye or nose. They are kept out of the production area until the Production Manager is satisfied they are fit to return, with medical clearance where needed.

## 4. Personal hygiene rules
- Wash and dry hands before starting work, after every break, after using the toilet, after handling waste or chemicals, and whenever hands may be dirty.
- Fingernails are short, clean and free of polish; no jewellery, watches or loose items are worn in the production area.
- Cuts and sores are covered with a waterproof, coloured dressing; a glove is worn over a hand injury.
- Eating, drinking, chewing, smoking, spitting and keeping personal items are prohibited in the production area.
- Coughing or sneezing over product is never permitted; hands are washed afterwards.

## 5. Hand-washing steps
1. Wet hands with running water.
2. Apply soap and rub palms, backs of hands, between fingers and thumbs for at least 20 seconds.
3. Rinse thoroughly under running water.
4. Dry with a single-use towel or a hand dryer.

## 6. Protective clothing
- White coats or clean overalls, hair nets (and beard nets where needed) and clean closed footwear or gumboots are worn by everyone in the production area.
- Gloves are worn where the task requires and are changed whenever they are torn or contaminated.
- Protective clothing is supplied by the company, kept clean, and is not worn outside the production area, including in toilets.
- Visitors, auditors and contractors are issued the same protective clothing before entering, and sign the visitors' book.
- Everyone passes through the foot bath on entering the production area. The foot-bath solution is renewed daily.

## 7. Training
- New staff are trained in this procedure before starting work and sign to confirm they understand it.
- Refresher training is given at least once a year and recorded in the Employees module (Training).

## 8. Supervision
Supervisors check that clothing, hand-washing and conduct are correct at the start of every shift and record any lapse and the action taken.

## 9. Records and review
Medical certificates, training records, the visitors' book and supervision records are kept for at least two years. This procedure is reviewed every year.
""",
    },
    {
        "code": "SOP-007",
        "title": "Quality Control Procedure",
        "category": Procedure.QC,
        "owner": "Quality Controller",
        "content": """## 1. Purpose
To make sure all packaged drinking water released by Fontis Springs meets the requirements of KS EAS 153:2018 (Packaged Drinking Water) and is labelled according to KS EAS 38:2014, by checking raw materials, the process and the finished product.

## 2. Scope
Source water, packaging materials, treatment, filling, capping, labelling, storage and dispatch.

## 3. Responsibilities
| Role | Responsibility |
| --- | --- |
| Quality Controller | Runs the checks, keeps records, releases or holds product, keeps the current standards at the laboratory |
| Production Manager | Makes sure no product is dispatched until released; acts on non-conformities |
| Machine and treatment operators | Carry out the routine in-process checks and report anything abnormal |

## 4. Reference documents
The current copies of KS EAS 153:2018, KS EAS 38:2014 and KS EAS 459 (Code of Hygiene) are kept in the laboratory and in the Compliance module. All limits and test methods are taken from the standard, not from memory.

## 5. Checks
| Stage | What is checked | How often | Recorded in |
| --- | --- | --- | --- |
| Source water | Appearance, pH, TDS, conductivity | Every day of production; full analysis at an accredited laboratory at the frequency in the Scheme of Supervision | Lab Test module |
| Packaging materials (bottles, caps, labels, cartons) | Supplier documents, damage, cleanliness, correct label | Every delivery | Receiving record |
| Treatment (filtration, reverse osmosis, disinfection) | Settings, pressure, pH, TDS, conductivity, disinfectant in operation | At start of production and at least every shift | Lab Test module |
| Filling and capping | Fill volume, cap fit and seal, absence of foreign matter | At start, then at intervals through the run | Production record |
| Labelling and coding | Label content against KS EAS 38:2014, batch code and dates legible | Every batch | Production record |
| Finished product (physical-chemical) | pH, TDS, conductivity, appearance, taste and odour | Every batch | Lab Test module |
| Finished product (microbiological and full chemical) | Parameters in KS EAS 153:2018 | At the frequency in the Scheme of Supervision, by an accredited laboratory | Laboratory reports on file |
| Cleaning effectiveness | Rinse-water or surface test on filling equipment | At the frequency set by the Quality Controller | Quality record |
| Retained samples | One sealed sample kept from each batch until the end of its shelf life | Every batch | Retained-sample log |

## 6. Procedure
1. **Raw materials.** Check packaging and chemicals against the specification when delivered. Reject or hold anything damaged, dirty, unlabelled or without supplier documents.
2. **Process.** Operators record the readings in section 5. If a reading falls outside its limit, stop filling, correct the fault, and hold all product made since the last good reading.
3. **Instruments.** Use only instruments that are in calibration (SOP-008). Check them daily with standard solutions where applicable.
4. **Sampling.** Take samples at random from each batch; keep a sealed retained sample and label it with the batch code and date.
5. **Release.** The Quality Controller releases a batch only when every required result meets the standard. Release is recorded against the batch code.
6. **Non-conforming product.** Hold it in the quarantine area, label it, investigate the cause, and decide with the Production Manager whether to reprocess (only if it can be made fully compliant) or destroy it (SOP-004). Record the decision and the corrective action.
7. **Trend review.** Review results each month for drift or repeated problems and act before limits are exceeded.

## 7. Competence
Quality control work is done by staff whose qualifications and evidence of employment are on file in the Compliance module (QC Personnel).

## 8. Records and review
Test results, production records, release records, laboratory reports and retained-sample logs are kept for at least two years, or for the shelf life of the product plus one year if that is longer. This procedure is reviewed every year.
""",
    },
    {
        "code": "SOP-008",
        "title": "Equipment Calibration Procedure",
        "category": Procedure.CALIBRATION,
        "owner": "Quality Controller",
        "content": """## 1. Purpose
To make sure every instrument whose reading affects product quality is accurate and traceable.

## 2. Scope
Critical measuring equipment, for example the pH meter, TDS and conductivity meter, thermometers, weighing scales, and any device used to control or check fill volume, pressure or flow.

## 3. Register
Every critical instrument is entered in the Compliance module (Calibration) with its name, serial number and location, so its calibration status and due date can be seen at a glance.

## 4. External calibration
1. Each instrument is calibrated at least once a year, or sooner if the manufacturer or the calibration laboratory requires, by a laboratory competent to do so (for example one accredited, or traceable to national standards).
2. The laboratory issues a calibration certificate stating the date, the results against the reference and the next due date.
3. The certificate is scanned and attached to the instrument's record. The system warns 30 days before a calibration expires.
4. A label showing the date calibrated and the date due is fixed to the instrument.

## 5. Routine checks between calibrations
- pH meters are checked each day of use against fresh buffer solutions, and adjusted if needed.
- TDS and conductivity meters are checked against a standard solution at least weekly.
- Scales are checked with a reference weight before use.
- Results are recorded with the date and the initials of the person checking.

## 6. When an instrument fails or is overdue
1. Stop using it and label it "Out of service".
2. Review the results taken since its last good check, and decide whether any batch needs to be re-tested or held.
3. Repair or replace it, and calibrate it again before it is used.
4. Record what happened, what was reviewed and what was decided.

## 7. Records and review
Calibration certificates, routine check records and failure reviews are kept for at least two years. This procedure is reviewed every year.
""",
    },
    {
        "code": "SOP-009",
        "title": "Scheme of Supervision and Control",
        "category": Procedure.SUPERVISION,
        "owner": "Managing Director",
        "content": """## 1. Firm and product
| Item | Details |
| --- | --- |
| Name of firm | Fontis Springs |
| Physical address of the premises |  |
| Contact person and telephone |  |
| Product(s) covered | Packaged drinking water |
| Brand name(s) and pack sizes |  |
| Applicable standards | KS EAS 153:2018 Packaged Drinking Water; KS EAS 38:2014 Labelling of Pre-Packaged Foods; KS EAS 459 Code of Hygiene |

## 2. Commitment
Fontis Springs undertakes to produce only packaged drinking water that complies with the standards above, to operate the quality-control system described in this scheme, and to allow KEBS officers access to the premises, records and samples at any reasonable time.

## 3. Organisation and responsibility
| Position | Name | Responsibility |
| --- | --- | --- |
| Managing Director |  | Overall responsibility for quality and for this scheme |
| Production Manager |  | Production, hygiene, maintenance and release of product |
| Quality Controller |  | All quality-control testing and records; holds or releases product |
| Hygiene Supervisor |  | Cleaning, personal hygiene, pest control and waste |

The qualifications and evidence of employment of the quality-control staff are held on file.

## 4. Process flow
1. Source water received or drawn.
2. Treatment: filtration, reverse osmosis or equivalent, and disinfection.
3. Treated-water storage.
4. Cleaning and sanitising of containers; filling; capping and sealing.
5. Coding and labelling.
6. Storage of finished goods.
7. Dispatch and delivery.

## 5. Control of materials
Source water, bottles, caps, labels, cartons and treatment chemicals are inspected on receipt against their specification and are used only if accepted (SOP-007).

## 6. Quality-control plan
| Stage | Test or check | Frequency |
| --- | --- | --- |
| Source water | pH, TDS, conductivity, appearance | Each production day |
| Treatment | Operating settings and readings | Start of production and each shift |
| Filling and sealing | Fill volume, closure, cleanliness | Start and during the run |
| Labelling | Content against KS EAS 38:2014, batch code and dates | Each batch |
| Finished product | Physical and chemical checks in-house | Each batch |
| Finished product | Microbiological and full analysis by an accredited laboratory | At the frequency agreed with KEBS |

Detailed methods, limits and responsibilities are in the Quality Control Procedure (SOP-007).

## 7. Equipment and calibration
All critical measuring equipment is listed, calibrated and checked as set out in SOP-008, and its calibration certificates are kept.

## 8. Hygiene, pest control and waste
The premises and staff are controlled under SOP-005 (cleaning and sanitation), SOP-006 (personal hygiene and medical fitness), SOP-003 (pest control) and SOP-004 (waste management).

## 9. Non-conforming product, complaints and recall
Product that does not meet the standard is held, investigated and disposed of as set out in SOP-007. Customer complaints are handled under SOP-002 and a recall, if ever needed, under SOP-001.

## 10. Records
Records of testing, production, cleaning, pest control, waste, calibration, complaints and training are kept for at least two years and are available to KEBS on request.

## 11. Declaration
We confirm that the information in this scheme is correct and that it will be followed.

| | Name | Signature | Date |
| --- | --- | --- | --- |
| For Fontis Springs (Managing Director) |  |  |  |
| KEBS officer |  |  |  |

Note: if KEBS gives you its own Scheme of Supervision and Control format, use this document as the source for it. Upload the signed copy to the Compliance module under Licences & Permits.
""",
    },
]

PREMISES_REQUIREMENTS = [
    ("premises_suitable", "Premises are structurally suitable and hygienically maintained, meeting KS EAS 459 (Code of Hygiene) and the Public Health Act (Cap 254)"),
    ("protective_clothing", "Protective clothing (white coats, hair nets) is provided to all staff and to visitors"),
    ("hand_wash", "Hand-wash point with running water and a means of drying hands"),
    ("steel_tables", "Stainless steel tables, or a suitable alternative, for production"),
    ("foot_bath", "Foot bath at the entrance to the production area"),
    ("label_conforms", "Product label conforms to KS EAS 38:2014 and the product standard"),
]
