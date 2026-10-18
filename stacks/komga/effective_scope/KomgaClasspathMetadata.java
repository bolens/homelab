import java.io.*;
import java.nio.*;
import java.nio.channels.*;
import java.nio.file.*;
import java.nio.file.attribute.*;
import java.security.*;
import java.util.*;
import java.util.jar.*;
import java.util.zip.*;

/** Public image metadata only; never puts application/Spring JARs on classpath. */
public final class KomgaClasspathMetadata {
 static final String APP_SHA="f76aff7d31f2735ed902e3a004540e869568be42dc099a5560d72fd3d8f2c0fe";
 static final String COMMIT="2ab7a5a61a8b8bb12a6edd576fed380b4b613c99";
 static final String[] EXPECTED={"lib/HdrHistogram-2.2.2.jar","lib/HikariCP-6.3.3.jar","lib/LatencyUtils-2.0.3.jar","lib/accessors-smart-2.5.2.jar","lib/annotations-13.0.jar","lib/asm-9.7.1.jar","lib/attoparser-2.0.7.RELEASE.jar","lib/byteunits-0.9.1.jar","lib/caffeine-3.2.4.jar","lib/classmate-1.7.3.jar","lib/common-image-3.14.0.jar","lib/common-io-3.14.0.jar","lib/common-lang-3.14.0.jar","lib/commons-beanutils-1.11.0.jar","lib/commons-codec-1.19.0.jar","lib/commons-collections-3.2.2.jar","lib/commons-compress-1.28.0.jar","lib/commons-digester-2.1.jar","lib/commons-io-2.22.0.jar","lib/commons-lang3-3.20.0.jar","lib/commons-logging-1.4.0.jar","lib/commons-validator-1.11.0.jar","lib/content-type-2.2.jar","lib/core-3.5.4.jar","lib/cryptohash-jvm-1.0.2.jar","lib/error_prone_annotations-2.49.0.jar","lib/flyway-core-11.7.2.jar","lib/fontbox-3.0.8.jar","lib/hibernate-validator-8.0.3.Final.jar","lib/icu4j-78.3.jar","lib/imageio-common-1.1.0.jar","lib/imageio-core-3.14.0.jar","lib/imageio-heif-1.1.0.jar","lib/imageio-jpeg-3.14.0.jar","lib/imageio-jxl-1.1.0.jar","lib/imageio-metadata-3.14.0.jar","lib/imageio-tiff-3.14.0.jar","lib/imageio-webp-1.1.0.jar","lib/imageio-webp-3.14.0.jar","lib/jackson-annotations-2.21.jar","lib/jackson-core-2.21.4.jar","lib/jackson-databind-2.21.4.jar","lib/jackson-dataformat-toml-2.21.4.jar","lib/jackson-dataformat-xml-2.21.4.jar","lib/jackson-dataformat-yaml-2.21.4.jar","lib/jackson-datatype-jdk8-2.21.4.jar","lib/jackson-datatype-jsr310-2.21.4.jar","lib/jackson-module-kotlin-2.21.4.jar","lib/jackson-module-parameter-names-2.21.4.jar","lib/jai-imageio-core-1.4.0.jar","lib/jai-imageio-jpeg2000-1.4.0.jar","lib/jakarta.activation-api-2.1.4.jar","lib/jakarta.annotation-api-2.1.1.jar","lib/jakarta.validation-api-3.0.2.jar","lib/jakarta.xml.bind-api-4.0.5.jar","lib/jbig2-imageio-3.0.5.jar","lib/jboss-logging-3.6.3.Final.jar","lib/jcip-annotations-1.0-1.jar","lib/jooq-3.19.35.jar","lib/json-smart-2.5.2.jar","lib/jsoup-1.23.1.jar","lib/jspecify-1.0.0.jar","lib/jul-to-slf4j-2.0.18.jar","lib/junrar-8.1.0.jar","lib/kotlin-logging-jvm-8.0.4.jar","lib/kotlin-reflect-2.4.10.jar","lib/kotlin-stdlib-2.4.10.jar","lib/lang-tag-1.7.jar","lib/log4j-api-2.24.3.jar","lib/log4j-to-slf4j-2.24.3.jar","lib/logback-classic-1.5.34.jar","lib/logback-core-1.5.34.jar","lib/lucene-analysis-common-9.9.1.jar","lib/lucene-backward-codecs-9.9.1.jar","lib/lucene-core-9.9.1.jar","lib/lucene-queries-9.9.1.jar","lib/lucene-queryparser-9.9.1.jar","lib/lucene-sandbox-9.9.1.jar","lib/micrometer-commons-1.15.12.jar","lib/micrometer-core-1.15.12.jar","lib/micrometer-jakarta9-1.15.12.jar","lib/micrometer-observation-1.15.12.jar","lib/natural-comparator-1.1.jar","lib/netty-buffer-4.1.135.Final.jar","lib/netty-codec-4.1.135.Final.jar","lib/netty-codec-dns-4.1.135.Final.jar","lib/netty-codec-http-4.1.135.Final.jar","lib/netty-codec-http2-4.1.135.Final.jar","lib/netty-codec-socks-4.1.135.Final.jar","lib/netty-common-4.1.135.Final.jar","lib/netty-handler-4.1.135.Final.jar","lib/netty-handler-proxy-4.1.135.Final.jar","lib/netty-resolver-4.1.135.Final.jar","lib/netty-resolver-dns-4.1.135.Final.jar","lib/netty-resolver-dns-classes-macos-4.1.135.Final.jar","lib/netty-resolver-dns-native-macos-4.1.135.Final-osx-x86_64.jar","lib/netty-transport-4.1.135.Final.jar","lib/netty-transport-classes-epoll-4.1.135.Final.jar","lib/netty-transport-native-epoll-4.1.135.Final-linux-x86_64.jar","lib/netty-transport-native-unix-common-4.1.135.Final.jar","lib/nimbus-jose-jwt-9.37.4.jar","lib/oauth2-oidc-sdk-9.43.6.jar","lib/pdfbox-3.0.8.jar","lib/pdfbox-io-3.0.8.jar","lib/r2dbc-spi-1.0.0.RELEASE.jar","lib/reactive-streams-1.0.4.jar","lib/reactor-core-3.7.19.jar","lib/reactor-netty-core-1.2.18.jar","lib/reactor-netty-http-1.2.18.jar","lib/slf4j-api-2.0.18.jar","lib/snakeyaml-2.5.jar","lib/spring-aop-6.2.19.jar","lib/spring-beans-6.2.19.jar","lib/spring-boot-3.5.16.jar","lib/spring-boot-actuator-3.5.16.jar","lib/spring-boot-actuator-autoconfigure-3.5.16.jar","lib/spring-boot-autoconfigure-3.5.16.jar","lib/spring-context-6.2.19.jar","lib/spring-context-support-6.2.19.jar","lib/spring-core-6.2.19.jar","lib/spring-data-commons-3.5.13.jar","lib/spring-expression-6.2.19.jar","lib/spring-jcl-6.2.19.jar","lib/spring-jdbc-6.2.19.jar","lib/spring-security-config-6.5.11.jar","lib/spring-security-core-6.5.11.jar","lib/spring-security-crypto-6.5.11.jar","lib/spring-security-oauth2-client-6.5.11.jar","lib/spring-security-oauth2-core-6.5.11.jar","lib/spring-security-oauth2-jose-6.5.11.jar","lib/spring-security-web-6.5.11.jar","lib/spring-session-caffeine-2.1.0.jar","lib/spring-session-core-3.5.7.jar","lib/spring-tx-6.2.19.jar","lib/spring-web-6.2.19.jar","lib/spring-webflux-6.2.19.jar","lib/spring-webmvc-6.2.19.jar","lib/springdoc-openapi-starter-common-2.8.9.jar","lib/springdoc-openapi-starter-webmvc-api-2.8.9.jar","lib/springdoc-openapi-starter-webmvc-ui-2.8.9.jar","lib/sqlite-jdbc-3.53.2.1.jar","lib/stax2-api-4.2.2.jar","lib/swagger-annotations-jakarta-2.2.30.jar","lib/swagger-core-jakarta-2.2.30.jar","lib/swagger-models-jakarta-2.2.30.jar","lib/swagger-ui-5.21.0.jar","lib/thumbnailator-0.4.21.jar","lib/thymeleaf-3.1.5.RELEASE.jar","lib/thymeleaf-spring6-3.1.5.RELEASE.jar","lib/tika-core-3.3.2.jar","lib/tomcat-embed-core-10.1.55.jar","lib/tomcat-embed-el-10.1.55.jar","lib/tomcat-embed-websocket-10.1.55.jar","lib/tsid-creator-5.2.6.jar","lib/unbescape-1.1.6.RELEASE.jar","lib/webjars-locator-lite-1.1.3.jar","lib/woodstox-core-7.1.1.jar"};
 static final String[] RESOURCES={"META-INF/MANIFEST.MF","META-INF/spring.factories",
 "META-INF/spring/org.springframework.boot.env.EnvironmentPostProcessor.imports",
 "META-INF/spring/org.springframework.boot.context.config.ConfigDataLocationResolver.imports",
 "META-INF/spring/org.springframework.boot.context.config.ConfigDataLoader.imports",
 "META-INF/spring/org.springframework.boot.env.PropertySourceLoader.imports",
 "META-INF/services/org.springframework.boot.env.EnvironmentPostProcessor",
 "META-INF/services/org.springframework.boot.context.config.ConfigDataLocationResolver",
 "META-INF/services/org.springframework.boot.context.config.ConfigDataLoader",
 "META-INF/services/org.springframework.boot.env.PropertySourceLoader",
 "META-INF/services/org.springframework.core.io.ProtocolResolver",
 "META-INF/services/java.nio.file.spi.FileSystemProvider"};
 static final int MAX_METADATA=4*1024*1024;
 static int metadataBytes=0;
 static void require(boolean b,String code){if(!b)throw new IllegalStateException(code);}
 static List<Long> nine(Path p,boolean follow)throws IOException{
  Map<String,Object>a=Files.readAttributes(p,"unix:dev,ino,size,lastModifiedTime,ctime,mode,uid,gid,nlink",follow?new LinkOption[]{}:new LinkOption[]{LinkOption.NOFOLLOW_LINKS});
  return List.of(((Number)a.get("dev")).longValue(),((Number)a.get("ino")).longValue(),((Number)a.get("size")).longValue(),((FileTime)a.get("lastModifiedTime")).to(java.util.concurrent.TimeUnit.NANOSECONDS),((FileTime)a.get("ctime")).to(java.util.concurrent.TimeUnit.NANOSECONDS),((Number)a.get("mode")).longValue(),((Number)a.get("uid")).longValue(),((Number)a.get("gid")).longValue(),((Number)a.get("nlink")).longValue());
 }
 static Set<String> fds()throws IOException{
  Set<String>names=new HashSet<>();Path own=Path.of("/proc/"+ProcessHandle.current().pid()+"/fd");int count=0;
  try(DirectoryStream<Path>d=Files.newDirectoryStream(Path.of("/proc/self/fd"))){for(Path f:d){require(++count<=256,"fd-bound");try{if(!Files.readSymbolicLink(f).equals(own))names.add(f.getFileName().toString());}catch(NoSuchFileException ignored){}}}
  return names;
 }
 static Path opened(Set<String>before,Path p,List<Long>original)throws IOException{
  List<Path>found=new ArrayList<>();for(String name:fds())if(!before.contains(name)){Path f=Path.of("/proc/self/fd",name);try{if(Files.readSymbolicLink(f).equals(p)&&nine(f,true).equals(original))found.add(f);}catch(NoSuchFileException ignored){}}
  require(found.size()==1,"opened-fd-identity");return found.get(0);
 }
 static String hash(FileChannel f)throws Exception{
  MessageDigest digest=MessageDigest.getInstance("SHA-256");ByteBuffer b=ByteBuffer.allocate(65536);f.position(0);long total=0;int n;
  while((n=f.read(b))!=-1){require(n>0&&((total+=n)<=256L*1024*1024),"jar-stream-bound");digest.update(b.array(),0,n);b.clear();}
  return HexFormat.of().formatHex(digest.digest());
 }
 static byte[] resource(ZipFile z,String name)throws IOException{
  ZipEntry e=z.getEntry(name);if(e==null)return null;require(!e.isDirectory()&&e.getSize()>=0&&e.getSize()<=262144,"resource-bound");
  try(InputStream in=z.getInputStream(e)){byte[]raw=in.readNBytes(262145);require(raw.length==e.getSize()&&raw.length<=262144&&in.read()==-1,"resource-length");CRC32 crc=new CRC32();crc.update(raw);require(crc.getValue()==e.getCrc(),"resource-crc");metadataBytes+=raw.length;require(metadataBytes<=MAX_METADATA,"metadata-total");return raw;}
 }
 static Map<String,Object>readJar(Path p,boolean application)throws Exception{
  require(p.isAbsolute()&&!Files.isSymbolicLink(p),"jar-path");List<Long>original=nine(p,false);require((original.get(5)&0170000)==0100000&&original.get(8)==1&&original.get(2)>0&&original.get(2)<=256L*1024*1024,"jar-original");
  Set<String>before=fds();try(FileChannel f=FileChannel.open(p,StandardOpenOption.READ,LinkOption.NOFOLLOW_LINKS)){
   Path fd=opened(before,p,original);require(nine(fd,true).equals(original)&&f.size()==original.get(2),"opened-original");String digest=hash(f);Map<String,String>resources=new LinkedHashMap<>();
   try(ZipFile z=new ZipFile(p.toFile())){
    int count=0;Set<String>names=new HashSet<>();Enumeration<? extends ZipEntry>entries=z.entries();while(entries.hasMoreElements()){String n=entries.nextElement().getName();require(++count<=100000&&names.add(n),"jar-entry-census");}
    for(String name:RESOURCES){byte[]raw=resource(z,name);if(raw!=null)resources.put(name,Base64.getEncoder().encodeToString(raw));}
    if(application){require(digest.equals(APP_SHA),"application-sha");byte[]manifest=resource(z,"META-INF/MANIFEST.MF");require(manifest!=null,"application-manifest");Attributes a=new Manifest(new ByteArrayInputStream(manifest)).getMainAttributes();require("1.28.1".equals(a.getValue("Implementation-Version"))&&"3.5.16".equals(a.getValue("Spring-Boot-Version")),"application-version");require(Arrays.equals(EXPECTED,a.getValue("Class-Path").trim().split(" +")),"exact-classpath");byte[]git=resource(z,"git.properties");require(git!=null,"application-git");Properties props=new Properties();props.load(new ByteArrayInputStream(git));require(COMMIT.equals(props.getProperty("git.commit.id"))&&"false".equals(props.getProperty("git.dirty")),"application-commit");resources.put("git.properties",Base64.getEncoder().encodeToString(git));}
   }
   require(nine(p,false).equals(original)&&nine(fd,true).equals(original)&&hash(f).equals(digest),"jar-original-final");Map<String,Object>result=new LinkedHashMap<>();result.put("path",p.toString());result.put("sha256",digest);result.put("signature9",original);result.put("resources_base64",resources);return result;
  }
 }
 static String quote(String s){StringBuilder b=new StringBuilder("\"");for(int i=0;i<s.length();i++){char c=s.charAt(i);switch(c){case '\"':b.append("\\\"");break;case '\\':b.append("\\\\");break;case '\n':b.append("\\n");break;case '\r':b.append("\\r");break;case '\t':b.append("\\t");break;default:if(c<32)b.append(String.format("\\u%04x",(int)c));else b.append(c);}}return b.append('\"').toString();}
 static String json(Object v){if(v instanceof String)return quote((String)v);if(v instanceof Boolean||v instanceof Number)return v.toString();if(v instanceof Map){List<String>x=new ArrayList<>();for(Object k:((Map<?,?>)v).keySet())x.add(quote(k.toString())+":"+json(((Map<?,?>)v).get(k)));return "{"+String.join(",",x)+"}";}if(v instanceof Iterable){List<String>x=new ArrayList<>();for(Object e:(Iterable<?>)v)x.add(json(e));return "["+String.join(",",x)+"]";}throw new IllegalArgumentException("json-type");}
 static void run()throws Exception{
  require(EXPECTED.length==157&&new HashSet<>(Arrays.asList(EXPECTED)).size()==157,"classpath-count");Path app=Path.of("/app/application.jar");Map<String,Object>main=readJar(app,true);List<Map<String,Object>>libs=new ArrayList<>();
  for(String relative:EXPECTED){require(relative.matches("lib/[A-Za-z0-9._-]+\\.jar"),"classpath-name");libs.add(readJar(Path.of("/app").resolve(relative),false));}
  require(nine(app,false).equals(main.get("signature9")),"application-final");for(Map<String,Object>v:libs)require(nine(Path.of((String)v.get("path")),false).equals(v.get("signature9")),"whole-map-final");
  Map<String,Object>out=new LinkedHashMap<>();out.put("kind","public-komga-classpath-metadata-v1");out.put("application",main);out.put("classpath",Arrays.asList(EXPECTED));out.put("dependencies",libs);out.put("metadata_bytes",metadataBytes);out.put("spring_initialized",false);out.put("application_initialized",false);out.put("configured_acceptance",false);System.out.println(json(out));
 }
 public static void main(String[]args){try{require(args.length==0,"no-arguments");run();}catch(Throwable e){Set<String>codes=Set.of("fd-bound","opened-fd-identity","jar-stream-bound","resource-bound","resource-length","resource-crc","metadata-total","jar-path","jar-original","opened-original","jar-entry-census","application-sha","application-manifest","application-version","exact-classpath","application-git","application-commit","jar-original-final","classpath-count","classpath-name","application-final","whole-map-final","no-arguments");System.err.println("public-classpath-metadata-refused:"+e.getClass().getSimpleName()+":"+(codes.contains(e.getMessage())?e.getMessage():"unclassified"));System.exit(2);}}
}
