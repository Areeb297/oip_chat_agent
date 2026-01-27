export interface FAQQuestion {
  id: string;
  question: string;
  answer: string;
}

export interface FAQCategory {
  id: string;
  title: string;
  description: string;
  questions: FAQQuestion[];
}

export const faqCategories: FAQCategory[] = [
  {
    id: 'platform-overview',
    title: 'Platform Overview',
    description: 'General information about the Ebttikar OIP system',
    questions: [
      {
        id: 'what-is-oip',
        question: 'What is Ebttikar Operations Intelligence Platform (OIP)?',
        answer:
          'It is a web-based platform that centralizes operational workflows. It monitors daily engineer activity, productivity, and ticket progress. It supports spreadsheet-style daily log entry and enforces approval workflows for daily logs and ticket closure requests. It also supports standardized templates for bulk uploads and ticket creation from both client-side and internal new installations.',
      },
      {
        id: 'delivery-roadmap',
        question: 'How does the delivery roadmap work?',
        answer:
          'Phase 1 delivers unified templates, bulk ticket upload, spreadsheet daily log entry, team lead approval workflows, SLA calculation, and core dashboards. Phase 2 delivers internal ticket creation, inventory and asset module, BTR travel cost management, and certification tracker. Phase 3 delivers AI operational agents, mobile application, and predictive analytics.',
      },
    ],
  },
  {
    id: 'administration',
    title: 'Administration and Access Control',
    description: 'User management, roles, and permissions',
    questions: [
      {
        id: 'user-management',
        question: 'What does user management cover?',
        answer:
          'It covers full lifecycle management for system users, including create, update, and delete operations.',
      },
      {
        id: 'roles-permissions',
        question: 'How do roles, permissions, and audit logs work?',
        answer:
          'Admins create roles dynamically. Permissions apply at page level and function level. Audit logging tracks user activity including login history and ticket updates.',
      },
    ],
  },
  {
    id: 'tickets-templates',
    title: 'Tickets and Templates',
    description: 'Ticket creation, templates, and routing',
    questions: [
      {
        id: 'ticket-template-fields',
        question: 'What fields are required in the unified ticket template?',
        answer:
          'Required fields include Project, Project ID, Ticket ID, Engineer, Employee ID, Region, Site Name, and Created Date. The template also supports optional fields such as Completed Date, City, Task Type, Description, Branch Name, Resolution Notes, Latitude, and Longitude. Delay Days is calculated automatically.',
      },
      {
        id: 'bulk-upload',
        question: 'How does bulk ticket upload work?',
        answer:
          'Users download the template, fill it, and upload it. The system validates fields and maps the Source System automatically. It supports validation, duplicate detection, and export.',
      },
      {
        id: 'internal-ticket-creation',
        question: 'How does internal ticket creation work for new installations?',
        answer:
          'Project Coordinator creates the ticket inside OIP. The system routes it to the Regional Team Lead. Regional Team Lead assigns it to a Field Engineer. Field Engineers and Team Leads do not create tickets, and the Create Ticket button stays hidden or disabled for them.',
      },
      {
        id: 'client-side-tickets',
        question: 'Who creates client-side tickets and how does routing work?',
        answer:
          'Customers and Project Coordinators create tickets. Team Leads and Field Engineers do not create tickets. After submission, the system routes the ticket to the Team Lead for the selected region. Regions include Riyadh, Eastern, South, West, North, and Qassim. The Team Lead assigns the ticket to a Field Engineer in the same region.',
      },
      {
        id: 'ticket-closure',
        question: 'How does client-side ticket closure work?',
        answer:
          'Engineer attaches closure report with supporting evidence such as images and documents. Engineer submits the ticket as Closed. Ticket closure does not require approval for this client-side flow. Engineer confirms closure after customer verbal verification. Team Lead does not approve or reject closure.',
      },
      {
        id: 'dependency-reporting',
        question: 'What is dependency and incident reporting, and what happens in out-of-scope work?',
        answer:
          'If a ticket cannot be closed due to external constraints, the engineer raises an Incident Report instead of closure. Dependency categories include Permit Required, Joint Visit Required, Power Issue, AC Not Working, Branch Closed, Manager Not Available, Network Issue, Out of Scope Activity, and Others. Out of Scope Activity triggers a workflow where a supplementary quotation is prepared and submitted to the customer for approval before additional work proceeds. After the dependency resolves, the engineer removes the dependency flag, completes the work, attaches the final report, and submits closure.',
      },
    ],
  },
  {
    id: 'daily-logs-sla',
    title: 'Daily Activity Logs and SLA',
    description: 'Activity logging and SLA tracking',
    questions: [
      {
        id: 'daily-logs',
        question: 'How do engineers enter daily activity logs?',
        answer:
          'Engineers enter logs inside an Excel-style table in the system. Employee ID is auto-retrieved from the session. Work Date is assigned per row. Columns include Site Name, TT PM Number, Activity, Ticket Status, Time Started, Time Ended, Remote Visit, Project, Remarks, Distance Travelled, Overtime, and Hotel Stay. TT PM Number supports selecting an existing ticket from inside the table. Distance Travelled is required only when Remote Visit equals Yes.',
      },
      {
        id: 'sla-calculation',
        question: 'How does SLA delay calculation work?',
        answer:
          'The system calculates delay days automatically. It excludes weekends (Friday and Saturday). It applies a 24-hour grace period. It supports picture uploads during ticket closure and customizable SLA rules by project.',
      },
    ],
  },
  {
    id: 'approvals-workflows',
    title: 'Approvals and Closure Workflows',
    description: 'Approval processes and closure procedures',
    questions: [
      {
        id: 'daily-approval',
        question: 'How does daily activity approval work and who can edit overtime?',
        answer:
          'When an engineer submits logs, the system stores them as pending_review and sets is_visible to false for Manager and Admin. Before approval, Team Lead can edit overtime up or down. The final approved log reflects the Team Lead edits.',
      },
      {
        id: 'closure-approval',
        question: 'How does ticket closure approval work inside OIP?',
        answer:
          'Path 1: Automatic closure happens when an Excel re-upload includes Closed status and Completed Date and validation passes. Path 2: Engineer submits a closure request inside OIP and it routes to Team Lead for approval, then the ticket closes on approval. Engineer attaches visual proof such as images or reports for validation.',
      },
    ],
  },
  {
    id: 'travel-compliance',
    title: 'Travel and Compliance',
    description: 'BTR tracking and certification management',
    questions: [
      {
        id: 'btr-tracker',
        question: 'What is the BTR travel tracker logic?',
        answer:
          'One-way trip qualifies as 1 BTR day when distance is at least 120 km and recorded activity exists. Two-way trip qualifies when total distance is at least 240 km. Return next day counts as a separate BTR day. If Distance Travelled is entered, the engineer cannot enter Overtime Hours for that day. Hotel Stay records hotel nights for reimbursement.',
      },
      {
        id: 'certification-tracker',
        question: 'How does the certification tracker enforce compliance?',
        answer:
          'Engineers cannot be defined or active without uploading required certificates, and the system blocks profile creation when certificate fields stay empty. When assigning an engineer, the system checks the engineer profile against certification requirements defined by Admin for the client or project. If the engineer lacks the required valid certificate, the system blocks assignment and prompts selection of a qualified engineer. The system sends expiry notifications 30, 15, and 7 days before expiry to the engineer and management.',
      },
    ],
  },
  {
    id: 'inventory-reporting',
    title: 'Inventory, Communications, and Reporting',
    description: 'Asset management, notifications, and dashboards',
    questions: [
      {
        id: 'inventory-tracking',
        question: 'How does inventory tracking work and who approves material requests?',
        answer:
          'Every inventory item uses barcode printers and scanners. Scanning updates inventory status and tracks location and condition. Field Engineers request items with Site ID, TR Call ID, and project info. Approval chain is Engineer, then Supervisor/Team Lead, then Operations Manager. Logistic Supervisor releases items and stays outside the approval chain.',
      },
      {
        id: 'delegation-notifications',
        question: 'What delegation, communication, and notification features exist, and what dashboards are included?',
        answer:
          'Delegation supports temporary reassignment of tickets and approvals when an engineer or team lead is on leave. Communication panel provides built-in chat with rooms and supports messages, images, videos, and admin visibility. Notification hub sends alerts via Email or WhatsApp for SLA breaches, expiring certificates, pending approvals, and status updates. Dashboards include ticket counts by status, region, and engineer. They include productivity, activity, SLA metrics, and approval metrics plus KPI oversight such as rejection rates and approval turnaround time.',
      },
    ],
  },
];
