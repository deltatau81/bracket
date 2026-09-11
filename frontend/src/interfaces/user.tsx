export type UserAccountType = 'REGULAR' | 'ADMIN' | 'SCORER' | 'DEMO';

export interface UserInterface {
  id: number;
  created: string;
  name: string;
  email: string;
  account_type: UserAccountType;
}

export interface UserBodyInterface {
  name: string;
  email: string;
}

export interface UserToRegisterInterface {
  name: string;
  email: string;
  password: string;
}

export interface UserAdminCreateInterface {
  name: string;
  email: string;
  password: string;
  account_type: 'ADMIN' | 'SCORER';
}
