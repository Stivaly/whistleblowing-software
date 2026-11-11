import {AppDataService} from "@app/app-data.service";
import {ChangeDetectorRef, Component, Input, OnInit, inject} from "@angular/core";
import {WbtipService} from "@app/services/helper/wbtip.service";
import {AuthenticationService} from "@app/services/helper/authentication.service";
import {UtilsService} from "@app/shared/services/utils.service";
import {ReceiverTipService} from "@app/services/helper/receiver-tip.service";
import {Comment} from "@app/models/app/shared-public-model";
import {PreferenceResolver} from "@app/shared/resolvers/preference.resolver";
import {MaskService} from "@app/shared/services/mask.service";
import {DatePipe} from "@angular/common";
import {FormsModule} from "@angular/forms";
import {NgbTooltipModule} from "@ng-bootstrap/ng-bootstrap";
import {TranslateModule} from "@ngx-translate/core";
import {TranslatorPipe} from "@app/shared/pipes/translate";
import {AutoExpandDirective} from "@app/shared/directive/auto-expand.directive";
import {PaginatedInterfaceComponent} from "@app/shared/components/paginated-interface/paginated-interface.component";
import {esNotaKerna} from "@app/shared/partials/kerna/kerna-notas";


@Component({
    selector: "src-tip-comments",
    templateUrl: "./tip-comments.component.html",
    standalone: true,
    imports: [AutoExpandDirective, DatePipe, FormsModule, NgbTooltipModule, PaginatedInterfaceComponent, TranslateModule, TranslatorPipe]
})
export class TipCommentsComponent implements OnInit {
  private maskService = inject(MaskService);
  protected preferenceResolver = inject(PreferenceResolver);
  private rTipService = inject(ReceiverTipService);
  protected authenticationService = inject(AuthenticationService);
  protected utilsService = inject(UtilsService);
  private cdr = inject(ChangeDetectorRef);
  appDataService = inject(AppDataService);

  @Input() tipService: ReceiverTipService | WbtipService;
  @Input() key: string;
  @Input() redactMode: boolean;
  @Input() redactOperationTitle: string;

  collapsed = false;
  newCommentContent = "";
  comments: Comment[] = [];
  newComments: Comment;

  ngOnInit() {
    this.comments = this.tipService.tip.comments;
  }

  public toggleCollapse() {
    this.collapsed = !this.collapsed;
  }

  newComment() {
    const response = this.tipService.newComment(this.newCommentContent, this.key);
    this.newCommentContent = "";

    response.subscribe(
      (data) => {
        this.comments = this.tipService.tip.comments;
        this.tipService.tip.comments.push(data);
        this.comments = [...this.comments, this.newComments];
        this.cdr.detectChanges();
      }
    );
  }

  getSortedComments(data: Comment[]): Comment[] {
    return data;
  }

  private cacheOrigen: Comment[] | null = null;
  private cacheLongitud = -1;
  private cacheVisibles: Comment[] = [];

  /**
   * Comentarios a mostrar. Para el destinatario se omiten las notas JSON de Kerna (sugerencia, estado, valoración y
   * clasificación), que muestra el bloque de Kerna en lugar de texto crudo. El denunciante no cambia: nunca las recibe.
   */
  get comentariosVisibles(): Comment[] {
    const todos = this.tipService.tip.comments;
    if (!todos || this.authenticationService.session?.role !== "receiver") {
      return todos;
    }
    if (todos !== this.cacheOrigen || todos.length !== this.cacheLongitud) {
      this.cacheOrigen = todos;
      this.cacheLongitud = todos.length;
      this.cacheVisibles = todos.filter(c => c.type || !esNotaKerna(c.content));
    }
    return this.cacheVisibles;
  }

  redactInformation(type:string, id:string, entry:string, content:string){
    this.maskService.redactInfo(type,id,entry,content,this.tipService.tip)
  }

  maskContent(id: string, index: string, value: string) {
    return this.maskService.maskingContent(id,index,value,this.tipService.tip)
  }
}
