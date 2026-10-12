export class statisticsResolverModel {
  reports_count: number;
  reports_with_no_access: number;
  reports_anonymous: number;
  reports_subscribed: number;
  reports_initially_anonymous: number;
  reports_mobile: number;
  reports_tor: number;
  reports_last_30_days: number;
  reports_important: number;
  reports_by_status: {[key: string]: number};
  average_access_count: number;
  reports_with_files: number;
}