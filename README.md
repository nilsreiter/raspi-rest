# Raspi Rest

This repository provides a simple REST API for things attached to a Raspberry Pi. The API is called from Home Assistant.

## LED Matrix

### Home Assistant



```yaml
notify:
  - name: led_matrix
    platform: rest
    resource: http://IPADDRESS:5000/message
    method: POST_JSON
    title_param_name: title
    message_param_name: message
    data:
      "contrast": "{{ data.contrast if (data.contrast is defined) else 255 }}"
      "scroll_delay": "{{ data.scroll_delay if (data.scroll_delay is defined) else 0.06 }}"
      "message": "{{ message }}"
```


```yaml
switch:
  - platform: rest
    resource: http://IPADDRESS:5000/state
    method: POST
    unique_id: led_matrix_state
    name: "LED-Matrix-Zustand"
    body_on: >-
      { "state": "time" }
    body_off: >-
      { "state": "off" }
    headers:
      Content-Type: application/json
    is_on_template: >-
      {{ value_json.state == "time" }}

```