# 2026 LPL Financial University Hackathon - Project Brief and Team Ideation Guide

> Shared source of truth for ideation, scope, implementation, presentation, and submission.
>
> Event dates: Friday, October 2 and Saturday, October 3, 2026  
> Theme: **Startup from the Future - Build the Startup LPL Would Want to Buy**

Event context: nearly 350 people applied; the event includes about 160 participants from 55 universities across 34 teams.

## 1. The challenge

Envision the future of wealth management and build a **compliant, AI-powered startup** that solves a meaningful challenge for one or more of these audiences:

- Financial advisors
- Investors
- Teams that support advisors or investors

The team must then pitch **why LPL should acquire the startup**.

The decks do not define a detailed regulatory-compliance framework. At minimum, follow the concrete privacy, synthetic-data, access-control, and storage rules in this brief, explain the product's compliance boundaries, and do not claim controls the prototype does not implement.

### Non-negotiable project requirements

- [ ] Solve a meaningful wealth-management problem for advisors, investors, or their support teams.
- [ ] Make the solution AI-powered.
- [ ] Build a working prototype or demo. The AWS workshop frames the target as a working agent.
- [ ] Use at least one AWS service.
- [ ] Use only hackathon-approved models from the allowlist in Section 2.
- [ ] Use made-up/synthetic data only - never personal data or real financial data.
- [ ] If using S3, keep every bucket private. Public S3 buckets are prohibited.
- [ ] Use the provided LPL PowerPoint template for the final presentation.
- [ ] Submit the required deliverables by **9:00 AM PT / 12:00 PM ET on October 3**.
- [ ] Select exactly 2 of the 4 main award categories. Every project is also automatically judged for Best Use of AWS.
- [ ] Remain available during the judging period.
- [ ] Collaborate within the assigned team.

### Required acquisition story

The pitch should make clear:

1. Who the startup helps.
2. What painful or important problem it solves.
3. What becomes easier or better for the user.
4. Why the opportunity matters to LPL.
5. Why LPL should buy this startup rather than merely build around the problem.
6. Why the team chose this design and these AWS services.

## 2. Hard AWS environment constraints

Treat these as build constraints, not suggestions:

- **Region:** Work in `us-east-1` (N. Virginia). If access is denied, check the selected region first.
- **Models:** Use Amazon Bedrock for model access and choose only from the hackathon model allowlist below. GPU instances are blocked in the provided accounts.
- **Rate limit:** Plan for about **1 Bedrock call per second**. Add a short pause to loops so the demo is not throttled.
- **Data:** Use synthetic/made-up data only. Do not use personal data or real financial data.
- **Storage security:** Never make an S3 bucket public.
- **Account lifetime:** The event AWS accounts will be deleted after the hackathon. Regularly push code to the team's own GitHub repository or download backups.

### Hackathon model allowlist

**Only the following models will be available for use during the hackathon.** The agent and any supporting embedding, reranking, or multimodal components must use models from this list:

- **Amazon Nova:** Micro, Lite, Pro, Nova 2 Lite, Nova 2 Sonic, and Nova Multimodal Embeddings
- **Amazon Titan:** Titan Embeddings
- **Anthropic Claude:** Sonnet 5, Opus 5, Fable 5, Opus 4.8, Opus 4.7, Opus 4.6, Sonnet 4.6, Opus 4.5, Sonnet 4.5, and Haiku 4.5
- **Cohere:** Embed English, Embed Multilingual, Embed v4, and Rerank 3.5
- **DeepSeek:** DeepSeek-R1
- **Meta Llama:** Llama 3, 3.1, 3.3, and 4. **Llama 3.2 is not available.**
- **Mistral AI:** All models
- **OpenAI:** GPT-5.4, GPT-5.5, GPT-5.6 Luna, GPT-5.6 Sol, and GPT-5.6 Terra
- **TwelveLabs:** Marengo 3.0 and Pegasus 1.2
- **Writer:** Palmyra X4 and Palmyra X5

Before implementation, verify that the specific model ID selected in Bedrock corresponds to one of the allowed names above. Embedding and reranking models support retrieval pipelines; select a generation/reasoning-capable model from the allowlist for the agent itself.

Additional engineering expectations emphasized by the AWS judging guidance:

- Do not hard-code credentials or keys.
- Use tight, least-privilege permissions.
- Handle errors gracefully.
- Choose a right-sized model.
- Choose AWS services because the solution needs them, not to inflate the service count.
- Prefer a small, working, explainable agent over an ambitious system that does not work.

## 3. What must be submitted

### Required deliverables

- [ ] Final presentation deck built with the provided LPL PowerPoint template
- [ ] Working prototype or demo
- [ ] ZIP file containing the project code
- [ ] Completed Project Submission Form

### Optional but recommended supporting material

- [ ] Recorded demo video as a backup
- [ ] Design mockups
- [ ] Technical documentation
- [ ] Architecture diagram

### Submission procedure

- Submit once per team.
- Upload the presentation deck and code ZIP to the team's assigned Box folder.
- Complete the Project Submission Form.
- Deadline: **Saturday, October 3 at 9:00 AM PT / 12:00 PM ET**.

## 4. Judging and awards

### Category selection

- At **12:00 PM PT / 3:00 PM ET on October 2**, teams receive a form to choose **2 of the 4 main categories** below.
- Every team is automatically considered for **Best Use of AWS**.
- Each project is therefore evaluated in **3 categories total**: 2 selected main categories plus Best Use of AWS.

### Main award categories and criteria

| Category | What judges evaluate |
| --- | --- |
| **Startup We'd Buy Tomorrow** | Clear value proposition; market opportunity; business viability; differentiation |
| **Best Technical Execution** | Functionality; technical complexity; implementation quality; scalability |
| **Biggest Business Impact** | Problem significance; measurable business value; scalability; impact potential |
| **Best Customer Experience** | User needs; usability; intuitiveness; overall user experience |

### Sponsor category: Best Use of AWS

The AWS deck lists these in priority order:

1. **Use AWS well:** Select the right service for the right reason.
2. **Build it right:** Be secure, reliable, cost-aware, performant, and appropriately scoped. Avoid hard-coded keys; use tight permissions, graceful errors, and a right-sized model.
3. **Solve a real problem:** Address something an advisor or investor would genuinely want fixed.
4. **Make it work:** Show a live, functioning demo rather than only slides.
5. **Tell the story:** Explain who it helps, why it matters, and why it was built this way.

Bottom line from the AWS session: **a small agent that works and can be explained beats an ambitious one that does not.**

### Presentation and judging format

- Judging: **October 3, 9:30-11:00 AM PT / 12:30-2:00 PM ET**.
- Presentation: **5 minutes**.
- Judge Q&A: **5 minutes**.
- Each breakout room has 2 LPL judges, 1 AWS judge, and 1 moderator.
- A separate presentation rubric covering deck content and judging expectations will be sent by the organizers.
- After judging, judges deliberate and choose category winners.
- Winning teams present again during the Closing Ceremony to LPL and AWS leaders.

The executive audience named in the opening deck includes Nitesh Ambastha (EVP and Chief Information Officer), Abhishek Sharma (EVP, Wealth Management Technology), Mamatha Pathipati (SVP, Technology), and John Stevens (SVP, AI Product Management).

### Awards

Five winning teams receive:

- A **$100 Amazon gift card for each team member**.
- Priority consideration for LPL Financial early-career opportunities for eligible winning-team members.

## 5. Full event schedule

### Day 1 - Friday, October 2

| Pacific Time | Eastern Time | Event |
| --- | --- | --- |
| 8:00-9:00 AM | 11:00 AM-12:00 PM | Opening Ceremony: opening remarks, rules and prompt reveal (8:00-8:15 PT); Billy Runyun executive segment (8:15-8:30 PT); AWS leadership segment (8:30-8:55 PT) |
| 9:00-9:30 AM | 12:00-12:30 PM | Hackathon begins |
| 9:30-10:30 AM | 12:30-1:30 PM | AWS demo and account setup support |
| 10:30-11:00 AM | 1:30-2:00 PM | AWS Q&A / mini office hours |
| 12:00 PM | 3:00 PM | Project category selection opens |
| 1:00-2:00 PM | 4:00-5:00 PM | AWS technical office hours |
| 5:00-6:00 PM | 8:00-9:00 PM | AWS technical office hours |

Office-hour signup details:

- The signup sheet is scheduled to be posted in Webex around **11:00 AM PT / 2:00 PM ET**.
- Office hours are optional.
- Choose one available 15-minute slot and breakout room.
- Enter the team number without overwriting another team's signup.

### Day 2 - Saturday, October 3

| Pacific Time | Eastern Time | Event |
| --- | --- | --- |
| 3:00-4:00 AM | 6:00-7:00 AM | Morning office hours |
| **9:00 AM** | **12:00 PM** | **Final submission and presentation upload deadline** |
| 9:30-11:00 AM | 12:30-2:00 PM | Team presentations and judging: 5-minute presentation plus 5-minute Q&A |
| 11:00-11:30 AM | 2:00-2:30 PM | Judging deliberation |
| 11:30 AM-12:30 PM | 2:30-3:30 PM | Closing Ceremony and awards; category winner announcements and winning-team presentations |

## 6. AWS build menu - recommendations, not extra requirements

The AWS session describes the following as a menu, not a required blueprint. Use only what the selected idea needs.

### Step 1: Define the need

- One-line format: **For [user], it [does a task] so they [get a result].**
- Choose the single flow the team will demonstrate live.
- Identify the synthetic data that flow needs.
- Define what "working" means before the submission deadline.

Before the workshop/build begins, make sure the team has its event AWS account access code and can enter the shared account.

### Step 2: Choose the interface

- Fastest start: **Streamlit** (`pip install` and build a simple page).
- Web application: AWS Amplify or CloudFront + S3.
- API: API Gateway + Lambda.
- Chat: Amazon Lex.

### Step 3: Add senses only if needed

- Fastest start: omit multimodal input, or allow the Bedrock model to read a file.
- Documents: Textract.
- Text processing: Comprehend or Translate.
- Voice: Transcribe, Polly, or Nova 2 Sonic.
- Images: Rekognition.

### Step 4: Build the agent

- Fastest start: **Strands Agents SDK for Python + a Bedrock model**.
- Observability: AgentCore Observability.
- Safety: Bedrock Guardrails.
- Runtime: AgentCore Runtime.
- Built-in capabilities: AgentCore Code Interpreter, Browser, or Gateway.
- Add memory only if the idea and demo flow genuinely need it.

### Step 5: Add tools and actions

- Fastest start: ordinary Python functions exposed as agent tools.
- Serverless compute: Lambda.
- Workflows: Step Functions or EventBridge.
- Notifications: SNS.
- A non-generative custom model, if genuinely needed: SageMaker AI on CPU (the deck gives XGBoost as an example).

### Step 6: Add knowledge and data

- Fastest start: Bedrock Knowledge Bases + S3.
- Search: S3 Vectors or OpenSearch.
- Application data: DynamoDB or RDS.
- Graph data: Neptune.
- Analytics: Athena, Glue, or Redshift.
- Recommendations: Personalize.

### Bedrock model guidance

Start with one model and switch only for a specific reason. Every model used must appear in the [hackathon model allowlist](#hackathon-model-allowlist); do not assume that another Bedrock model is available merely because it exists in the broader Bedrock catalog.

### Apply throughout the build

- Security: IAM least privilege, Secrets Manager, and KMS.
- Verification/operations: AWS Security Agent and CloudWatch.
- Reproducibility: CDK or Terraform where useful.
- Durability: push the code to the team's own Git repository.

### Quick wins highlighted by AWS

- A Streamlit page
- One agent with 2 or 3 tools
- Synthetic data in CSV or S3
- A Knowledge Base over a few PDFs
- A live demo from the IDE

### Time sinks to avoid during this hackathon

- A custom React front end
- A multi-agent setup on day one
- Real market-data feeds
- Training or fine-tuning models
- A full ECS/EKS deployment with real login

## 7. LPL context to ground ideation

The opening deck's LPL snapshot, dated June 30, 2026, provides useful scale and stakeholder context:

- Nearly 40 years providing investment solutions, technology platforms, resources, and services to U.S. financial advisors and institutions.
- Fortune 500, No. 264.
- Approximately 32,500 financial advisors.
- Approximately 1,100 financial institutions.
- More than 10,000 employees.
- Approximately $2.6 trillion in client assets.
- Offices shown in Boston, New York, the DC Metro/Arlington area, Fort Mill, Austin, Tempe, San Diego, and Hyderabad.
- The slide reports $6.2B in gross-profit contribution, split approximately across advisory fees and commissions (30%), client cash (29%), other asset-based revenue (24%), service and fee revenue (12%), transaction revenue (2%), net interest income (2%), and other revenue (1%).

Use this context to look for problems with meaningful reach, but do not use or invent real customer information. The prototype must still use synthetic data.

## 8. Team ideation workspace

> This section is a collaboration template created for the team. It is not an additional event requirement.

### 8.1 Candidate idea table

Add one row for every serious idea. Score each criterion from 1 (weak) to 5 (strong). Do not choose an idea merely because it uses more AWS services.

| Idea | Primary user | Pain/need | Why LPL buys it | Live-demo clarity | 1-day feasibility | Compliance/data safety | AWS fit | Chosen category fit | Total | Decision |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| | | | | | | | | | | |
| | | | | | | | | | | |
| | | | | | | | | | | |

### 8.2 Idea card - duplicate this for each finalist

#### Idea name: [working title]

- **One-line concept:** For [user], it [does a task] so they [get a result].
- **Primary user:**
- **Current pain:**
- **Why the pain is meaningful:**
- **Proposed experience:**
- **Single live-demo flow:**
- **What "working" means:**
- **Why AI is necessary:**
- **Why an agent is appropriate:**
- **Why LPL should acquire it:**
- **Differentiator:**
- **Measurable business/customer outcome:**
- **Synthetic demo data required:**
- **Compliance and safety boundaries:**
- **Chosen AWS services and the reason for each:**
- **Smallest build that proves the idea:**
- **Stretch features only after the core works:**
- **Biggest technical risk:**
- **Biggest story/pitch risk:**

### 8.3 Mandatory constraint gate

An idea should not advance until every answer is "yes."

- [ ] It fits the wealth-management theme.
- [ ] It helps an advisor, investor, or a team supporting them.
- [ ] It is AI-powered.
- [ ] It can become a working prototype by the deadline.
- [ ] It uses at least one AWS service for a defensible reason.
- [ ] Its agent and supporting AI components use only models on the hackathon allowlist.
- [ ] It can operate entirely on synthetic data.
- [ ] It can keep S3 private and avoid hard-coded credentials.
- [ ] It has a clear 5-minute live-demo story.
- [ ] The team can explain why LPL should acquire it.
- [ ] It strongly fits at least 2 main judging categories.

### 8.4 Category decision

Choose the two categories that match the product's genuine strengths.

| Category | Evidence we can show in 5 minutes | Strength (1-5) | Select? |
| --- | --- | ---: | --- |
| Startup We'd Buy Tomorrow | | | |
| Best Technical Execution | | | |
| Biggest Business Impact | | | |
| Best Customer Experience | | | |

**Selected categories:** 1. __________  2. __________

### 8.5 Proposed minimal architecture

Fill this in before building:

```text
[User]
   |
   v
[Interface]
   |
   v
[Agent + Bedrock model]
   |-- [Tool 1: purpose]
   |-- [Tool 2: purpose]
   `-- [Optional Tool 3: purpose]
   |
   v
[Private synthetic data / knowledge source]
```

Architecture decisions:

| Component | Choice | Why this choice | Owner | Status |
| --- | --- | --- | --- | --- |
| Interface | | | | |
| Bedrock model | | | | |
| Agent framework | | | | |
| Tool/action 1 | | | | |
| Tool/action 2 | | | | |
| Data store/knowledge | | | | |
| Security/permissions | | | | |
| Monitoring/error handling | | | | |

### 8.6 Team roles and workstreams

| Workstream | Owner | Backup/reviewer | Definition of done | Status |
| --- | --- | --- | --- | --- |
| Product/problem definition | | | | |
| Synthetic data | | | | |
| Agent/backend | | | | |
| Interface | | | | |
| AWS/security | | | | |
| Testing/demo reliability | | | | |
| Deck and acquisition story | | | | |
| Submission and backups | | | | |

### 8.7 Decision log

| Time | Decision | Why | Owner | Revisit only if... |
| --- | --- | --- | --- | --- |
| | | | | |

## 9. Demo and presentation checklist

### Five-minute presentation structure

This suggested structure maps directly to the judging criteria:

1. **Problem and user:** Who has the problem and why it matters.
2. **Startup and acquisition case:** What the product does and why LPL should buy it.
3. **Live demo:** Show the one end-to-end flow working.
4. **Architecture and AWS choices:** Explain what each service contributes and how the build is secure/reliable.
5. **Impact and close:** Quantify the potential value, identify the selected award categories, and restate the "why."

### Demo readiness

- [ ] The main flow works end to end.
- [ ] The demo uses synthetic data only.
- [ ] No secrets or credentials appear on screen or in the repository.
- [ ] S3 buckets are private.
- [ ] Bedrock calls are paced to avoid throttling.
- [ ] The system handles at least the likely failure cases gracefully.
- [ ] The team has a reset procedure and known-good demo inputs.
- [ ] A recorded demo exists as backup.
- [ ] Screenshots are available as a second backup.
- [ ] Each teammate knows who speaks, clicks, watches time, and answers technical/business questions.

### Likely Q&A topics to prepare

- Why this problem?
- Why this user?
- Why should LPL buy it?
- Why AI, and why an agent?
- Why these particular AWS services and this model?
- How is the solution compliant and safe?
- What data would a production version use, and how would it be protected?
- How does the solution scale?
- What measurable business or customer outcome does it create?
- What is working now versus future roadmap?

## 10. Final submission and account-shutdown checklist

### Before 9:00 AM PT / 12:00 PM ET on October 3

- [ ] Validate the final prototype from a clean start.
- [ ] Confirm the final deck uses the LPL template.
- [ ] Export/check the final deck on the machine used to present.
- [ ] Create and test the code ZIP.
- [ ] Remove secrets, local credentials, caches, and unnecessary large files from the ZIP.
- [ ] Include a concise README with setup, run, architecture, and demo instructions.
- [ ] Upload the deck and ZIP to the assigned Box folder.
- [ ] Complete the Project Submission Form.
- [ ] Confirm that only one team submission was made.
- [ ] Keep local/GitHub copies of the final code and deck.
- [ ] Remain available for judging and monitor Webex for the breakout-room assignment.

### Before the temporary AWS account is deleted

- [ ] Push/download all code and documentation.
- [ ] Save architecture diagrams and screenshots.
- [ ] Export any synthetic datasets the team wants to keep.
- [ ] Record configuration details needed to recreate the project.
- [ ] Complete the AWS workshop survey by selecting **Share feedback** in the workshop's left menu.

## 11. Support, rooms, and contacts

### Support channels

- Use the **Webex Support Chat** for event logistics, technical questions, or AWS support.
- Use the shared signup sheet for AWS office hours.
- AWS how-to library: <https://catalog.workshops.aws/genai-hackathon>
- Strands working-code samples: <https://github.com/strands-agents/samples>
- The AWS deck also points teams to AgentCore samples for advanced use.

### Judging-room grouping

The exact assigned room is sent before judging. The planned grouping is:

- Room 1: Teams 1-7
- Room 2: Teams 8-14
- Room 3: Teams 15-21
- Room 4: Teams 22-28
- Room 5: Teams 29-34

### Event contact

- Sama Ahmed: `sama.ahmed@lplfinancial.com`

### AWS session contacts

- Ravi Thakur: `rrthakur@amazon.com`
- Nandhini Balakrishnan: `nandzy@amazon.com`

## 12. Source notes and interpretation

This brief consolidates the project-relevant content from:

- *Opening Ceremony Deck - 2026 University Hackathon* (26 slides)
- *AWS Hackathon Onboarding Presentation* (9 slides)

Interpretation rules used in this file:

- Items explicitly required by the opening deck or stated as hard limits by AWS are labeled as requirements or constraints.
- AWS architecture options are labeled as recommendations, not mandatory services.
- The team worksheets, scoring table, suggested presentation sequence, and Q&A list are planning aids added to support collaboration; they are not official rules.
- Decorative slides, acknowledgements, and speaker biographies were not turned into project requirements.
- If a later organizer message, category form, presentation rubric, submission form, Box instruction, or Webex announcement conflicts with this file, the newer official instruction should control and this file should be updated.
