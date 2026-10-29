import { css } from "lit";

export const sharedStyles = css`
  :host {
    font-family: var(--ha-font-family-body, Roboto, Noto, sans-serif);
    color: var(--primary-text-color, #141414);
    -webkit-font-smoothing: var(--ha-font-smoothing, antialiased);
  }
  .visually-hidden {
    position: absolute;
    width: 1px;
    height: 1px;
    margin: -1px;
    padding: 0;
    overflow: hidden;
    clip: rect(0 0 0 0);
    white-space: nowrap;
    border: 0;
  }
  ha-svg-icon {
    flex: none;
  }
`;
