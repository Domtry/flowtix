import { Pipe, PipeTransform } from '@angular/core';
import { DomSanitizer, SafeHtml } from '@angular/platform-browser';

/** Trusts SVG markup. Only for the static icons of workflow-catalog.ts — never user input. */
@Pipe({ name: 'safeSvg', standalone: true })
export class SafeSvgPipe implements PipeTransform {
  constructor(private sanitizer: DomSanitizer) {}
  transform(markup: string): SafeHtml {
    return this.sanitizer.bypassSecurityTrustHtml(markup);
  }
}
