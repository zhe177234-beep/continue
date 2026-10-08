package cn.zhixue;

import jakarta.servlet.http.HttpServletRequest;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Duration;
import java.util.Set;

/** API boundary. Account/learning persistence lives in the Python service in v0.3. */
@RestController
public class GatewayController {
    private final HttpClient client = HttpClient.newBuilder().version(HttpClient.Version.HTTP_1_1).connectTimeout(Duration.ofSeconds(5)).build();
    private final String upstream;
    public GatewayController(@Value("${ai.url:http://127.0.0.1:8000}") String upstream) {
        this.upstream = upstream.replaceAll("/+$", "");
    }

    @RequestMapping("/api/**")
    public ResponseEntity<byte[]> forward(HttpServletRequest incoming) throws Exception {
        String method = incoming.getMethod();
        if (!Set.of("GET", "POST", "DELETE").contains(method)) return error(405, "不支持的请求方法");
        String origin = incoming.getHeader("Origin");
        if (!method.equals("GET") && origin != null) {
            try {
                if (!URI.create(origin).getAuthority().equals(incoming.getHeader("Host"))) return error(403, "不允许跨站请求");
            } catch (Exception ex) { return error(403, "无效来源"); }
        }
        byte[] body = incoming.getInputStream().readNBytes(3 * 1024 * 1024 + 65537);
        if (body.length > 3 * 1024 * 1024 + 65536) return error(413, "请求过大");
        // Encode the path only; never use an incoming URL/Host as the upstream target.
        String path = incoming.getRequestURI();
        if (!path.startsWith("/api/") || path.contains("..") || path.contains("%")) return error(400, "无效接口路径");
        HttpRequest.Builder request = HttpRequest.newBuilder(URI.create(upstream + path)).timeout(Duration.ofSeconds(210));
        for (String name : Set.of("Content-Type", "Cookie")) {
            String value = incoming.getHeader(name);
            if (value != null) request.header(name, value);
        }
        request.method(method, body.length == 0 ? HttpRequest.BodyPublishers.noBody() : HttpRequest.BodyPublishers.ofByteArray(body));
        try {
            HttpResponse<byte[]> response = client.send(request.build(), HttpResponse.BodyHandlers.ofByteArray());
            var result = ResponseEntity.status(response.statusCode());
            for (String name : Set.of("Content-Type", "Set-Cookie", "Cache-Control", "X-Content-Type-Options")) {
                for (String value : response.headers().allValues(name)) result.header(name, value);
            }
            return result.body(response.body());
        } catch (java.io.IOException ex) { return error(502, "AI 服务暂时不可用，请检查服务日志"); }
        catch (InterruptedException ex) { Thread.currentThread().interrupt(); return error(503, "请求已中断"); }
    }

    private ResponseEntity<byte[]> error(int status, String message) {
        return ResponseEntity.status(status).header("Content-Type", "application/json; charset=utf-8").body(("{\"detail\":\"" + message + "\"}").getBytes(java.nio.charset.StandardCharsets.UTF_8));
    }
}
