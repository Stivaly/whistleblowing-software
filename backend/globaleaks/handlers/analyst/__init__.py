# Handlers dealing with analyst user functionalities
import csv
from io import StringIO
from sqlalchemy.sql.expression import func, and_

from globaleaks import models
from globaleaks.handlers.base import BaseHandler
from globaleaks.orm import transact
from globaleaks.utils.utility import datetime_now

from datetime import timedelta


@transact
def get_stats(session, tid):
    """
    Transaction for retrieving analyst statistics

    :param session: An ORM session
    :param tid: A tenant ID
    """
    now = datetime_now()
    thirty_days_ago = now - timedelta(days=30)

    reports_count = session.query(func.count(models.InternalTip.id)) \
                           .filter(models.InternalTip.tid == tid).one()[0]

    num_tips_no_access = session.query(func.count(models.InternalTip.id)) \
                                .filter(models.InternalTip.tid == tid,
                                        models.InternalTip.access_count == 0).one()[0]

    num_tips_mobile = session.query(func.count(models.InternalTip.id)) \
                             .filter(models.InternalTip.tid == tid,
                                     models.InternalTip.mobile == True).one()[0]

    num_tips_tor = session.query(func.count(models.InternalTip.id)) \
                             .filter(models.InternalTip.tid == tid,
                                     models.InternalTip.tor == True).one()[0]

    num_subscribed_tips = session.query(func.count(models.InternalTip.id)) \
                                 .filter(models.InternalTip.tid == tid) \
                                 .join(models.InternalTipData,
                                       and_(models.InternalTipData.internaltip_id == models.InternalTip.id,
                                            models.InternalTipData.key == 'whistleblower_identity',
                                            models.InternalTipData.creation_date == models.InternalTip.creation_date)).one()[0]

    num_initially_anonymous_tips = session.query(func.count(models.InternalTip.id)) \
                                       .filter(models.InternalTip.tid == tid) \
                                       .join(models.InternalTipData,
                                             and_(models.InternalTipData.internaltip_id == models.InternalTip.id,
                                                  models.InternalTipData.key == 'whistleblower_identity',
                                                  models.InternalTipData.creation_date != models.InternalTip.creation_date)).one()[0]

    num_anonymous_tips = reports_count - num_subscribed_tips - num_initially_anonymous_tips

    # Métricas operacionales adicionales
    reports_last_30_days = session.query(func.count(models.InternalTip.id)) \
                                  .filter(models.InternalTip.tid == tid,
                                          models.InternalTip.creation_date >= thirty_days_ago).one()[0]

    reports_important = session.query(func.count(models.InternalTip.id)) \
                               .filter(models.InternalTip.tid == tid,
                                       models.InternalTip.important == True).one()[0]

    # Métricas de efectividad - por estado
    status_counts = session.query(models.InternalTip.status, func.count(models.InternalTip.id)) \
                           .filter(models.InternalTip.tid == tid) \
                           .group_by(models.InternalTip.status).all()

    status_dict = {status: count for status, count in status_counts}

    # Promedio de accesos por reporte
    avg_access = session.query(func.avg(models.InternalTip.access_count)) \
                        .filter(models.InternalTip.tid == tid).one()[0] or 0

    # Reportes con archivos adjuntos
    reports_with_files = session.query(func.count(func.distinct(models.InternalFile.internaltip_id))) \
                                .join(models.InternalTip,
                                      models.InternalFile.internaltip_id == models.InternalTip.id) \
                                .filter(models.InternalTip.tid == tid).one()[0]

    return {
        "reports_count": reports_count,
        "reports_with_no_access": num_tips_no_access,
        "reports_anonymous": num_anonymous_tips,
        "reports_subscribed": num_subscribed_tips,
        "reports_initially_anonymous": num_initially_anonymous_tips,
        "reports_mobile": num_tips_mobile,
        "reports_tor": num_tips_tor,
        "reports_last_30_days": reports_last_30_days,
        "reports_important": reports_important,
        "reports_by_status": status_dict,
        "average_access_count": round(float(avg_access), 2),
        "reports_with_files": reports_with_files
    }


@transact
def get_reports_export(session, tid):
    """
    Transaction for retrieving reports data for export

    :param session: An ORM session
    :param tid: A tenant ID
    """
    # Obtener nombre del tenant desde Config
    tenant_name_config = session.query(models.Config.value) \
                                .filter(models.Config.tid == tid,
                                        models.Config.var_name == 'name').one_or_none()
    tenant_name = tenant_name_config[0] if tenant_name_config else f"Tenant {tid}"

    # Obtener estados disponibles
    statuses = session.query(models.SubmissionStatus) \
                      .filter(models.SubmissionStatus.tid == tid).all()
    status_map = {s.id: s.label.get('en', s.label.get(list(s.label.keys())[0], 'Unknown')) if s.label else 'Unknown' for s in statuses}

    # Obtener reportes con sus datos
    reports = session.query(models.InternalTip) \
                     .filter(models.InternalTip.tid == tid) \
                     .order_by(models.InternalTip.creation_date.desc()).all()

    # Verificar identidad para cada reporte
    reports_with_identity = set()
    identity_data = session.query(models.InternalTipData.internaltip_id) \
                           .filter(models.InternalTipData.key == 'whistleblower_identity').all()
    for row in identity_data:
        reports_with_identity.add(row[0])

    # Contar archivos por reporte
    files_count = session.query(models.InternalFile.internaltip_id,
                                func.count(models.InternalFile.id)) \
                         .group_by(models.InternalFile.internaltip_id).all()
    files_map = {tip_id: count for tip_id, count in files_count}

    result = []
    for report in reports:
        status_label = status_map.get(report.status, 'Unknown')

        # Determinar tipo de anonimato
        if report.id in reports_with_identity:
            anonymity = "Subscribed"
        else:
            anonymity = "Anonymous"

        result.append({
            "tenant_name": tenant_name,
            "progressive": report.progressive,
            "creation_date": report.creation_date.strftime("%Y-%m-%d %H:%M:%S"),
            "update_date": report.update_date.strftime("%Y-%m-%d %H:%M:%S"),
            "status": status_label,
            "important": report.important,
            "mobile": report.mobile,
            "access_count": report.access_count,
            "anonymity": anonymity,
            "files_count": files_map.get(report.id, 0)
        })

    return result


class Statistics(BaseHandler):
    """
    Handler for statistics fetch
    """
    check_roles = 'analyst'

    def get(self):
        return get_stats(self.session.tid)


class ExportReports(BaseHandler):
    """
    Handler for exporting reports to CSV
    """
    check_roles = 'analyst'

    async def get(self):
        reports = await get_reports_export(self.session.tid)

        output = StringIO()
        writer = csv.writer(output)

        # Header
        writer.writerow([
            'Tenant',
            'Report #',
            'Creation Date',
            'Last Update',
            'Status',
            'Important',
            'Mobile',
            'Access Count',
            'Anonymity',
            'Files Count'
        ])

        # Data
        for report in reports:
            writer.writerow([
                report['tenant_name'],
                report['progressive'],
                report['creation_date'],
                report['update_date'],
                report['status'],
                'Yes' if report['important'] else 'No',
                'Yes' if report['mobile'] else 'No',
                report['access_count'],
                report['anonymity'],
                report['files_count']
            ])

        csv_content = output.getvalue()
        output.close()

        filename = f"reports_export_{datetime_now().strftime('%Y%m%d_%H%M%S')}.csv"

        self.request.setHeader('Content-Type', 'text/csv')
        self.request.setHeader('Content-Disposition', f'attachment; filename="{filename}"')

        return csv_content
