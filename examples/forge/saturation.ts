import { emit, event, field, refrigeration } from "./cstack";

export function signature(): void {
  emit("{\"version\":1,\"name\":\"ammonia_saturation_pressure\",\"inputs\":[{\"path\":\"temperature_c\",\"type\":\"number\",\"unit\":\"degC\",\"domain\":[-70,100]}],\"output\":{\"type\":\"number\",\"unit\":\"kPa(a)\"}}");
}

export function reduce(): void {
  const temperature = field(event(), "inputs.temperature_c");
  const receipt = refrigeration("saturation_pressure", "{\"fluid\":\"NH3\",\"temperature\":{\"value\":" + temperature + ",\"unit\":\"degC\"}}");
  emit("{\"value\":" + field(receipt, "result.pressure.value") + "}");
}
