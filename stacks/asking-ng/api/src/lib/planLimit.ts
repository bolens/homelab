export type PlanLimitRequiredPlan = 'cloud-team' | 'cloud-pro' | 'selfhost-pro' | 'enterprise-custom';

export function buildPlanLimitDetails(args: {
  plan: string;
  requiredPlan: PlanLimitRequiredPlan;
  feature: string;
}) {
  return {
    plan: args.plan,
    required_plan: args.requiredPlan,
    upgrade_hint: `${args.feature} requires ${args.requiredPlan} or higher.`,
  };
}
