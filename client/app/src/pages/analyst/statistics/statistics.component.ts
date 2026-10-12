import {Component, OnInit, inject} from '@angular/core';
import {StatisticsResolver} from '@app/shared/resolvers/statistics.resolver';
import {TranslateService, TranslateModule} from '@ngx-translate/core';
import {UtilsService} from '@app/shared/services/utils.service';
import {AuthenticationService} from '@app/services/helper/authentication.service';

import {BaseChartDirective, provideCharts, withDefaultRegisterables} from 'ng2-charts';
import {TranslatorPipe} from '@app/shared/pipes/translate';

@Component({
    selector: 'src-statistics',
    templateUrl: './statistics.component.html',
    standalone: true,
    imports: [
    BaseChartDirective,
    TranslateModule,
    TranslatorPipe
],
    providers: [provideCharts(withDefaultRegisterables())],
})
export class StatisticsComponent implements OnInit {
  private translateService = inject(TranslateService);
  private statisticsResolver = inject(StatisticsResolver);
  private utilsService = inject(UtilsService);
  private authenticationService = inject(AuthenticationService);

  // Secciones de métricas
  operationalMetrics: {charts: any[], stats: any} = {charts: [], stats: {}};
  effectivenessMetrics: {charts: any[], stats: any} = {charts: [], stats: {}};
  trustMetrics: {charts: any[], stats: any} = {charts: [], stats: {}};

  ngOnInit(): void {
    this.initializeCharts();
  }

  exportReports(): void {
    const filename = `reports_export_${new Date().toISOString().slice(0, 10)}.csv`;
    this.utilsService.saveAs(this.authenticationService, filename, 'api/analyst/export');
  }

  private calculatePercentage(value: number, total: number): string {
    if (total === 0) {
      return '0.0';
    }
    return ((value / total) * 100).toFixed(1);
  }

  private createChart(title: string, labels: string[], values: number[], colors: string[]) {
    let total = 0;
    let i: any;

    for (i in values) {
      total += values[i];
    }

    for (i in labels) {
      labels[i] = this.translateService.instant(labels[i]) + ": " + this.calculatePercentage(values[i], total) + "%";
    }

    return {
      title: this.translateService.instant(title),
      labels: labels,
      datasets: [{'labels': labels, 'data': values, 'backgroundColor': colors}],
      total: total,
    };
  }

  private initializeCharts(): void {
    const { dataModel } = this.statisticsResolver;
    const reports_count: number = dataModel.reports_count || 0;

    // === MÉTRICAS OPERACIONALES ===
    const mobile_yes: number = dataModel.reports_mobile || 0;
    const mobile_no: number = reports_count - mobile_yes;

    const with_files: number = dataModel.reports_with_files || 0;
    const without_files: number = reports_count - with_files;

    this.operationalMetrics.charts.push(
      this.createChart("Mobile", ["Yes", "No"], [mobile_yes, mobile_no], ["rgb(96,186,255)", "rgb(0,127,224)"])
    );
    this.operationalMetrics.charts.push(
      this.createChart("Reports with attachments", ["With files", "Without files"], [with_files, without_files], ["rgb(96,186,255)", "rgb(0,127,224)"])
    );
    this.operationalMetrics.stats = {
      total: reports_count,
      last30Days: dataModel.reports_last_30_days || 0,
      important: dataModel.reports_important || 0
    };

    // === MÉTRICAS DE EFECTIVIDAD ===
    const no_access: number = dataModel.reports_with_no_access || 0;
    const with_access: number = reports_count - no_access;

    this.effectivenessMetrics.charts.push(
      this.createChart("Returning whistleblowers", ["Yes", "No"], [with_access, no_access], ["rgb(96,186,255)", "rgb(0,127,224)"])
    );
    this.effectivenessMetrics.stats = {
      averageAccess: dataModel.average_access_count || 0,
      byStatus: dataModel.reports_by_status || {}
    };

    // === MÉTRICAS DE CONFIANZA Y SEGURIDAD ===
    const anonymous: number = dataModel.reports_anonymous || 0;
    const subscribed: number = dataModel.reports_subscribed || 0;
    const subscribed_later: number = dataModel.reports_initially_anonymous || 0;

    this.trustMetrics.charts.push(
      this.createChart("Anonymity", ["Anonymous", "Subscribed", "Subscribed later"], [anonymous, subscribed, subscribed_later], ["rgb(96,186,255)", "rgb(0,127,224)", "rgb(0,46,82)"])
    );
    this.trustMetrics.stats = {
      anonymousPercent: this.calculatePercentage(anonymous, reports_count),
      subscribedPercent: this.calculatePercentage(subscribed + subscribed_later, reports_count)
    };
  }
}
