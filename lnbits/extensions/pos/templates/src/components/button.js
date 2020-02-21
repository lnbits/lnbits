export const Button = ({ value, action }) => {
    let style;
    switch (value) {
      case "C":
        style = "btn-cancel";
        break;
      case "OK":
        style = "btn-confirm";
        break;
      default:
        style = "btn-numpad";
    }
    return (
      <button class={style} onClick={action}>
        {value}
      </button>
    );
  };