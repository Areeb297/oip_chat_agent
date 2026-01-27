// OIP User Context Constants
// These are hardcoded values for testing/development purposes
// In production, user data and roles should be fetched via stored procedures

export interface Project {
  code: string;
  name: string;
}

export interface Role {
  id: number;
  name: string;
  code: string;
}

export interface User {
  email: string;
  username: string;
  roleId: number;
  roleName: string;
  roleCode: string;
}

export const PROJECTS: Project[] = [
  { code: 'ANB', name: 'ANB' },
  { code: '1211', name: 'SABB' },
  { code: 'SAIB', name: 'Saudi Arabian Investment Bank' },
  { code: 'siib', name: 'saudi arabia test' },
  { code: 'Barclays', name: 'Barclays UK Bank PLC' },
  { code: 'Alinma', name: 'Alinma Bank' },
  { code: 'RAJHI', name: 'Al Rajhi Bank' },
];

export const TEAMS: string[] = [
  'Maintenance',
  'My Team',
  'Test Team',
  'New Team',
  'Ebttikar Physical Security',
  'Areeb Team',
  'Dream Team',
  'Jeddah Team',
  'Jubail Team',
  'Riyadh',
  'Makkah',
  'Madinah',
  'Qassim',
  'Eastern Province',
  'Asir',
  'Tabuk',
  'Hail',
  'Northern Borders',
  'Jizan',
  'Najran',
  'Al Bahah',
];

export const ROLES: Role[] = [
  { id: 1, name: 'Administrator', code: 'Administrator' },
  { id: 2, name: 'Field Engineer', code: 'FieldEngineer' },
  { id: 3, name: 'Cloud Administrator', code: 'CloudAdministrater' },
  { id: 4, name: 'Supervisor', code: 'TeamLead' },
  { id: 5, name: 'Logistics Supervisor', code: 'InventoryAdministrator' },
  { id: 6, name: 'Project Manager', code: 'ProjectManager' },
  { id: 7, name: 'Project Coordinator', code: 'ProjectCoordinator' },
  { id: 8, name: 'Resident Engineer', code: 'ResidentEngineer' },
  { id: 9, name: 'Operations Manager', code: 'OperationsManager' },
];

// Helper to get role by ID
export const getRoleById = (id: number): Role | undefined => ROLES.find(r => r.id === id);

// Users with their assigned roles
// Note: Users without explicit role mappings default to Field Engineer (roleId: 2)
export const USERS: User[] = [
  // Users with explicit role mappings
  { email: 'cloudadmin@cloudtech.com', username: 'cloudadmin', roleId: 3, roleName: 'Cloud Administrator', roleCode: 'CloudAdministrater' },
  { email: 'admin@ebttikar.com.sa', username: 'admin', roleId: 1, roleName: 'Administrator', roleCode: 'Administrator' },
  { email: 'projectmanager@ebttikar.com.sa', username: 'projectmanager', roleId: 6, roleName: 'Project Manager', roleCode: 'ProjectManager' },
  { email: 'projectcoordinator@ebttikar.com.sa', username: 'projectcoordinator', roleId: 7, roleName: 'Project Coordinator', roleCode: 'ProjectCoordinator' },
  { email: 'supervisor@ebttikar.com.sa', username: 'supervisor', roleId: 4, roleName: 'Supervisor', roleCode: 'TeamLead' },
  { email: 'fieldengineer@ebttikar.com.sa', username: 'fieldengineer', roleId: 2, roleName: 'Field Engineer', roleCode: 'FieldEngineer' },
  { email: 'logisticssupervisor@ebttikar.com.sa', username: 'logisticssupervisor', roleId: 5, roleName: 'Logistics Supervisor', roleCode: 'InventoryAdministrator' },
  { email: 'residentengineer@ebttikar.com.sa', username: 'residentengineer', roleId: 8, roleName: 'Resident Engineer', roleCode: 'ResidentEngineer' },
  { email: 'operationsmanager@ebttikar.com.sa', username: 'operationsmanager', roleId: 9, roleName: 'Operations Manager', roleCode: 'OperationsManager' },
  { email: 'areeb@ebttikar.com', username: 'areeb', roleId: 2, roleName: 'Field Engineer', roleCode: 'FieldEngineer' },
  { email: 'shamlankm@ebttikar.com', username: 'shamlankm', roleId: 1, roleName: 'Administrator', roleCode: 'Administrator' },
  { email: 'ahmad@ebttikar.com', username: 'ahmad', roleId: 1, roleName: 'Administrator', roleCode: 'Administrator' },
  // Users defaulting to Field Engineer
  { email: 'imran@ebttikar.com', username: 'imran', roleId: 2, roleName: 'Field Engineer', roleCode: 'FieldEngineer' },
  { email: 'atif@ebttikar.com', username: 'atif', roleId: 2, roleName: 'Field Engineer', roleCode: 'FieldEngineer' },
  { email: 'eyad@ebttikar.com', username: 'eyad', roleId: 2, roleName: 'Field Engineer', roleCode: 'FieldEngineer' },
  { email: 'hassan@ebttikar.com', username: 'hassan', roleId: 2, roleName: 'Field Engineer', roleCode: 'FieldEngineer' },
  { email: 'salman@ebttikar.com', username: 'salman', roleId: 2, roleName: 'Field Engineer', roleCode: 'FieldEngineer' },
  { email: 'ateeq@ebttikar.com', username: 'ateeq', roleId: 2, roleName: 'Field Engineer', roleCode: 'FieldEngineer' },
  { email: 'admin.etg@ebttikar.com', username: 'admin.etg', roleId: 1, roleName: 'Administrator', roleCode: 'Administrator' },
  { email: 'hayyal.naji@ebttikar.com', username: 'hayyal.naji', roleId: 2, roleName: 'Field Engineer', roleCode: 'FieldEngineer' },
  { email: 'faisal.bashir@ebttikar.com', username: 'faisal.bashir', roleId: 2, roleName: 'Field Engineer', roleCode: 'FieldEngineer' },
  { email: 'ranju.kallil@ebttikar.com', username: 'ranju.kallil', roleId: 2, roleName: 'Field Engineer', roleCode: 'FieldEngineer' },
  { email: 'sharif.khan@ebttikar.com', username: 'sharif.khan', roleId: 2, roleName: 'Field Engineer', roleCode: 'FieldEngineer' },
  { email: 'inamullah.khan@ebttikar.com', username: 'inamullah.khan', roleId: 2, roleName: 'Field Engineer', roleCode: 'FieldEngineer' },
  { email: 'sibghatullah.faseehullah@ebttikar.com', username: 'sibghatullah.faseehullah', roleId: 2, roleName: 'Field Engineer', roleCode: 'FieldEngineer' },
  { email: 'fayyaz.ahmad@ebttikar.com', username: 'fayyaz.ahmad', roleId: 2, roleName: 'Field Engineer', roleCode: 'FieldEngineer' },
  { email: 'ishfaq.ali@ebttikar.com', username: 'ishfaq.ali', roleId: 2, roleName: 'Field Engineer', roleCode: 'FieldEngineer' },
  { email: 'muhammad.muhammad@ebttikar.com', username: 'muhammad.muhammad', roleId: 2, roleName: 'Field Engineer', roleCode: 'FieldEngineer' },
  { email: 'muhammed.awan@ebttikar.com', username: 'muhammed.awan', roleId: 2, roleName: 'Field Engineer', roleCode: 'FieldEngineer' },
  { email: 'abuthar.batsha@ebttikar.com', username: 'abuthar.batsha', roleId: 2, roleName: 'Field Engineer', roleCode: 'FieldEngineer' },
  { email: 'nasrullah.saidin@ebttikar.com', username: 'nasrullah.saidin', roleId: 2, roleName: 'Field Engineer', roleCode: 'FieldEngineer' },
  { email: 'ali.mushtaq@ebttikar.com', username: 'ali.mushtaq', roleId: 2, roleName: 'Field Engineer', roleCode: 'FieldEngineer' },
  { email: 'sharif.shehata@ebttikar.com', username: 'sharif.shehata', roleId: 2, roleName: 'Field Engineer', roleCode: 'FieldEngineer' },
  { email: 'fehman.jassiddi@ebttikar.com', username: 'fehman.jassiddi', roleId: 2, roleName: 'Field Engineer', roleCode: 'FieldEngineer' },
  { email: 'malik.akbar@ebttikar.com', username: 'malik.akbar', roleId: 2, roleName: 'Field Engineer', roleCode: 'FieldEngineer' },
  { email: 'muhammad.ahmed@ebttikar.com', username: 'muhammad.ahmed', roleId: 2, roleName: 'Field Engineer', roleCode: 'FieldEngineer' },
  { email: 'hammad.mehmood@ebttikar.com', username: 'hammad.mehmood', roleId: 2, roleName: 'Field Engineer', roleCode: 'FieldEngineer' },
  { email: 'muhammad.habib@ebttikar.com', username: 'muhammad.habib', roleId: 2, roleName: 'Field Engineer', roleCode: 'FieldEngineer' },
  { email: 'mohammad.zahid@ebttikar.com', username: 'mohammad.zahid', roleId: 2, roleName: 'Field Engineer', roleCode: 'FieldEngineer' },
  { email: 'muhammad.akhtar@ebttikar.com', username: 'muhammad.akhtar', roleId: 2, roleName: 'Field Engineer', roleCode: 'FieldEngineer' },
  { email: 'waheed.syed@ebttikar.com', username: 'waheed.syed', roleId: 2, roleName: 'Field Engineer', roleCode: 'FieldEngineer' },
  { email: 'hammad.ali@ebttikar.com', username: 'hammad.ali', roleId: 2, roleName: 'Field Engineer', roleCode: 'FieldEngineer' },
  { email: 'muthaleeb.kaniyankandi@ebttikar.com', username: 'muthaleeb.kaniyankandi', roleId: 2, roleName: 'Field Engineer', roleCode: 'FieldEngineer' },
  { email: 'farmanullah.razzaq@ebttikar.com', username: 'farmanullah.razzaq', roleId: 2, roleName: 'Field Engineer', roleCode: 'FieldEngineer' },
  { email: 'muhammad.rahim@ebttikar.com', username: 'muhammad.rahim', roleId: 2, roleName: 'Field Engineer', roleCode: 'FieldEngineer' },
  { email: 'ali.thabet@ebttikar.com', username: 'ali.thabet', roleId: 2, roleName: 'Field Engineer', roleCode: 'FieldEngineer' },
  { email: 'asad.muhammad@ebttikar.com', username: 'asad.muhammad', roleId: 2, roleName: 'Field Engineer', roleCode: 'FieldEngineer' },
  { email: 'mudassar.hameed@ebttikar.com', username: 'mudassar.hameed', roleId: 2, roleName: 'Field Engineer', roleCode: 'FieldEngineer' },
  { email: 'ali.alwadai@ebttikar.com', username: 'ali.alwadai', roleId: 2, roleName: 'Field Engineer', roleCode: 'FieldEngineer' },
  { email: 'raja.yousuf@ebttikar.com', username: 'raja.yousuf', roleId: 2, roleName: 'Field Engineer', roleCode: 'FieldEngineer' },
  { email: 'muhammad.suleman@ebttikar.com', username: 'muhammad.suleman', roleId: 2, roleName: 'Field Engineer', roleCode: 'FieldEngineer' },
  { email: 'asim.qasem@ebttikar.com', username: 'asim.qasem', roleId: 2, roleName: 'Field Engineer', roleCode: 'FieldEngineer' },
  { email: 'tariq.din@ebttikar.com', username: 'tariq.din', roleId: 2, roleName: 'Field Engineer', roleCode: 'FieldEngineer' },
  { email: 'faisal.gul@ebttikar.com', username: 'faisal.gul', roleId: 2, roleName: 'Field Engineer', roleCode: 'FieldEngineer' },
  { email: 'muhammed.qayyum@ebttikar.com', username: 'muhammed.qayyum', roleId: 2, roleName: 'Field Engineer', roleCode: 'FieldEngineer' },
  { email: 'muhammad.mihas@ebttikar.com', username: 'muhammad.mihas', roleId: 2, roleName: 'Field Engineer', roleCode: 'FieldEngineer' },
  { email: 'najeeb.khan@ebttikar.com', username: 'najeeb.khan', roleId: 2, roleName: 'Field Engineer', roleCode: 'FieldEngineer' },
  { email: 'hassan.said@ebttikar.com', username: 'hassan.said', roleId: 2, roleName: 'Field Engineer', roleCode: 'FieldEngineer' },
  { email: 'muhammad.khan@ebttikar.com', username: 'muhammad.khan', roleId: 2, roleName: 'Field Engineer', roleCode: 'FieldEngineer' },
  { email: 'salah.mohiuddin@ebttikar.com', username: 'salah.mohiuddin', roleId: 2, roleName: 'Field Engineer', roleCode: 'FieldEngineer' },
  { email: 'muhammad.hameed@ebttikar.com', username: 'muhammad.hameed', roleId: 2, roleName: 'Field Engineer', roleCode: 'FieldEngineer' },
  { email: 'wasi.siddiqui@ebttikar.com', username: 'wasi.siddiqui', roleId: 2, roleName: 'Field Engineer', roleCode: 'FieldEngineer' },
  { email: 'marwan.thabit@ebttikar.com', username: 'marwan.thabit', roleId: 2, roleName: 'Field Engineer', roleCode: 'FieldEngineer' },
  { email: 'neil.paz@ebttikar.com', username: 'neil.paz', roleId: 2, roleName: 'Field Engineer', roleCode: 'FieldEngineer' },
  { email: 'aziz.wahab@ebttikar.com', username: 'aziz.wahab', roleId: 2, roleName: 'Field Engineer', roleCode: 'FieldEngineer' },
  { email: 'fida.room@ebttikar.com', username: 'fida.room', roleId: 2, roleName: 'Field Engineer', roleCode: 'FieldEngineer' },
  { email: 'muhammad.yousef@ebttikar.com', username: 'muhammad.yousef', roleId: 2, roleName: 'Field Engineer', roleCode: 'FieldEngineer' },
  { email: 'muhammad.aabid@ebttikar.com', username: 'muhammad.aabid', roleId: 2, roleName: 'Field Engineer', roleCode: 'FieldEngineer' },
  { email: 'saharukh.khan@ebttikar.com', username: 'saharukh.khan', roleId: 2, roleName: 'Field Engineer', roleCode: 'FieldEngineer' },
  { email: 'saeed.shafi@ebttikar.com', username: 'saeed.shafi', roleId: 2, roleName: 'Field Engineer', roleCode: 'FieldEngineer' },
  { email: 'rashid.rehman@ebttikar.com', username: 'rashid.rehman', roleId: 2, roleName: 'Field Engineer', roleCode: 'FieldEngineer' },
  { email: 'muhammad.jan@ebttikar.com', username: 'muhammad.jan', roleId: 2, roleName: 'Field Engineer', roleCode: 'FieldEngineer' },
  { email: 'anoop.sasidharan@ebttikar.com', username: 'anoop.sasidharan', roleId: 2, roleName: 'Field Engineer', roleCode: 'FieldEngineer' },
  { email: 'karim.khan@ebttikar.com', username: 'karim.khan', roleId: 2, roleName: 'Field Engineer', roleCode: 'FieldEngineer' },
  { email: 'muhammad.ullah@ebttikar.com', username: 'muhammad.ullah', roleId: 2, roleName: 'Field Engineer', roleCode: 'FieldEngineer' },
  { email: 'john.pedrosa@ebttikar.com', username: 'john.pedrosa', roleId: 2, roleName: 'Field Engineer', roleCode: 'FieldEngineer' },
  { email: 'vidal.fuertes@ebttikar.com', username: 'vidal.fuertes', roleId: 2, roleName: 'Field Engineer', roleCode: 'FieldEngineer' },
  { email: 'khalid.hussain@ebttikar.com', username: 'khalid.hussain', roleId: 2, roleName: 'Field Engineer', roleCode: 'FieldEngineer' },
  { email: 'govinda.beedubail@ebttikar.com', username: 'govinda.beedubail', roleId: 2, roleName: 'Field Engineer', roleCode: 'FieldEngineer' },
  { email: 'ahmed.d@ebttikar.com', username: 'ahmed.d', roleId: 2, roleName: 'Field Engineer', roleCode: 'FieldEngineer' },
  { email: 'abdulwahab.alqahtani@ebttikar.com', username: 'abdulwahab.alqahtani', roleId: 2, roleName: 'Field Engineer', roleCode: 'FieldEngineer' },
  { email: 'zainulhaq.mehmood@ebttikar.com', username: 'zainulhaq.mehmood', roleId: 2, roleName: 'Field Engineer', roleCode: 'FieldEngineer' },
  { email: 'haider.dad@ebttikar.com', username: 'haider.dad', roleId: 2, roleName: 'Field Engineer', roleCode: 'FieldEngineer' },
  { email: 'sabit.badshah@ebttikar.com', username: 'sabit.badshah', roleId: 2, roleName: 'Field Engineer', roleCode: 'FieldEngineer' },
  { email: 'amer.hussain@ebttikar.com', username: 'amer.hussain', roleId: 2, roleName: 'Field Engineer', roleCode: 'FieldEngineer' },
  { email: 'zeeshan.ahmad@ebttikar.com', username: 'zeeshan.ahmad', roleId: 2, roleName: 'Field Engineer', roleCode: 'FieldEngineer' },
  { email: 'salman.minhas@ebttikar.com', username: 'salman.minhas', roleId: 2, roleName: 'Field Engineer', roleCode: 'FieldEngineer' },
  { email: 'hussein.alakrash@ebttikar.com', username: 'hussein.alakrash', roleId: 2, roleName: 'Field Engineer', roleCode: 'FieldEngineer' },
  { email: 'rizwan.khan@ebttikar.com', username: 'rizwan.khan', roleId: 2, roleName: 'Field Engineer', roleCode: 'FieldEngineer' },
  { email: 'mohammed.munir@ebttikar.com', username: 'mohammed.munir', roleId: 2, roleName: 'Field Engineer', roleCode: 'FieldEngineer' },
  { email: 'muhammad.ahmed2@ebttikar.com', username: 'muhammad.ahmed2', roleId: 2, roleName: 'Field Engineer', roleCode: 'FieldEngineer' },
  { email: 'syed.quadri@ebttikar.com', username: 'syed.quadri', roleId: 2, roleName: 'Field Engineer', roleCode: 'FieldEngineer' },
  { email: 'usman.siddiqui@ebttikar.com', username: 'usman.siddiqui', roleId: 2, roleName: 'Field Engineer', roleCode: 'FieldEngineer' },
  { email: 'muhammad.saeed@ebttikar.com', username: 'muhammad.saeed', roleId: 2, roleName: 'Field Engineer', roleCode: 'FieldEngineer' },
  { email: 'kashif.raza@ebttikar.com', username: 'kashif.raza', roleId: 2, roleName: 'Field Engineer', roleCode: 'FieldEngineer' },
  { email: 'mohamed.elbana@ebttikar.com', username: 'mohamed.elbana', roleId: 2, roleName: 'Field Engineer', roleCode: 'FieldEngineer' },
  { email: 'razi.siddiqui@ebttikar.com', username: 'razi.siddiqui', roleId: 2, roleName: 'Field Engineer', roleCode: 'FieldEngineer' },
  { email: 'rehan.shehbaz@ebttikar.com', username: 'rehan.shehbaz', roleId: 2, roleName: 'Field Engineer', roleCode: 'FieldEngineer' },
];

// Helper to find user by username
export const getUserByUsername = (username: string): User | undefined =>
  USERS.find(u => u.username === username);
