import { ref } from "vue";

export type OperationMessageType = "info" | "error";

export function useOperationMessage() {
  const operationMessage = ref("");
  const operationMessageType = ref<OperationMessageType>("info");

  function setOperationMessage(message: string, type: OperationMessageType = "info") {
    operationMessage.value = message;
    operationMessageType.value = type;
  }

  return {
    operationMessage,
    operationMessageType,
    setOperationMessage,
  };
}
