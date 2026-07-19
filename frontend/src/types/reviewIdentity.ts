export type ReviewerRole = "physician" | "project_reviewer" | "engineering_reviewer" | "legacy_unverified";

export interface ReviewActorIdentity {
  actor_id: string;
  role: ReviewerRole;
  institution: string;
  auth_source: string;
}

export interface ReviewIdentityStatus extends ReviewActorIdentity {
  authenticated: boolean;
}
